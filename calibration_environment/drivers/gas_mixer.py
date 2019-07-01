import logging
import re
from collections import namedtuple
from enum import IntEnum
from typing import Tuple, List

import pandas as pd
import serial

""" Controls & monitoring for Osmo's Alicat gas mixing system
Assumptions:
 * system is one Alicat mix controller connected to 2 MFCs
 * MFC 1 is connected to a nitrogen supply
 * MFC 2 is connected to a supply containing oxygen (likely mixed with nitrogen

Mixer model details and API manuals are stored on our Google Drive:
   https://drive.google.com/drive/u/1/folders/1TFJ5s1ckozGHsIr4bARBcdym7e4Z011Q
   Note that Alicat won't share the full serial API with outsiders, but they have been open to
   providing any specific part of the reference.
"""

logger = logging.getLogger(__name__)

# Default baud rate - this can be reconfigured
_ALICAT_BAUD_RATE = 19200
_ALICAT_SERIAL_LINE_ENDING = "\r"

# The mixer we have is set to device ID "A"
_DEVICE_ID = "A"

# In response to a QMXS (query mixer status) command, the controller provides
# space-separated values matching these fields. Field names are adapted from the alicat serial protocol manual.
MixerStatusResponse = namedtuple(
    "MixerStatusResponse",
    [
        "device_id",
        "version",
        "mix_status",
        "mix_alarm",
        "pressure_units",
        "flow_units",
        "volume_units",
        "num_ports",
        "mix_alarm_enable",
        "gas_analyzer_alarm_enable",
        "mix_pressure",
        "mix_flow",
        "mix_volume",
        "gas_analyzer",
        # In the Alicat manual, the fields after this have the form [name]N where N is an MFC number.
        # Osmo's mix controller is connected to 2 MFCs.
        # #1 is for nitrogen and #2 is for the gas that we get oxygen from (referred to as the "O2 source gas").
        "n2_status",
        "n2_pressure",
        "n2_flow",
        "n2_total_volume",
        "n2_total_fraction",
        "o2_source_gas_status",
        "o2_source_gas_pressure",
        "o2_source_gas_flow",
        "o2_source_gas_total_volume",
        "o2_source_gas_total_fraction",
    ],
)

# In status fields, this bit is used to indicate low feed pressure,
# which generally means a cylinder is exhausted, not connected or there's a kink in the line
_LOW_FEED_PRESSURE_ALARM_BIT = 0x008000

_ONE_BILLION = 1000000000


class _MixControllerStateCode(IntEnum):
    emergency_motion_off = 0
    stopped_configuration_error = 1
    mixing = 2
    stopped_ok = 3
    stopped_error_silent = 4
    stopped_error = 5

    @property
    def description(self):
        return {
            0: "Emergency Motion Off (EMO) is active.",
            1: "Mixing is stopped and cannot be started because of an invalid configuration,"
            " usually an invalid mix fraction.",
            2: "Device is mixing.",
            3: "Mixing is stopped but can be started when desired.",
            4: "At least one alarm is active, but external indicators have been quieted.",
            5: "At least one alarm is active and triggering external indicators.",
        }[self]

    def __str__(self):
        return f'MixControllerState #{self.value}: "{self.description}"'

    def __format__(self, format_spec):
        # mixin'd subclasses of Enum have to override __format__ in addition to __str__ to change f-string behavior.
        # bug report:
        # https://bugs.python.org/issue37479?@ok_message=msg%20347089%20created%0Aissue%2037479%20created&@template=item
        return str(self)


_PRESSURE_UNIT_CODE_MMHG = 14
_FLOW_UNIT_CODE_SLPM = 7


class UnexpectedMixerResponse(Exception):
    # General error for when the mixer doesn't tell us what we expect it to.
    pass


def _assert_mixer_state(
    actual_response: str, expected_code: _MixControllerStateCode
) -> None:

    # Response will look something like "A 3" where "3" is the code
    regex = r"{device_id} (\d)".format(device_id=_DEVICE_ID)
    match = re.match(regex, actual_response)
    actual_code = _MixControllerStateCode(
        int(
            match.groups()[0]  # type: ignore # mypy issue with groups()
        )
    )

    if actual_code != expected_code:
        raise UnexpectedMixerResponse(
            f"Expected {expected_code!s} but received {actual_code!s}"
        )


def send_serial_command_str_and_get_response(command_str: str, port: str) -> str:
    """ Given a serial command, send it on a serial port and return the response.
    Handles Alicat default serial settings and line endings.

    Args:
        command_str: str of command to send, without termination character
        port: serial port to connect to, e.g. COM19 on Windows and /dev/ttyUSB0 on linux

    Returns:
        response, as a string with the alicat end-of-line character (carriage return) stripped
    """

    # Add the expected line ending and convert to bytes for serial transmission
    command_bytes = bytes(f"{command_str}{_ALICAT_SERIAL_LINE_ENDING}", encoding="utf8")

    logger.debug(f"Serial command: {command_bytes}")

    with serial.Serial(port, _ALICAT_BAUD_RATE, timeout=0.1) as connection:
        connection.write(command_bytes)
        return_value_with_line_ending = connection.read_until(
            _ALICAT_SERIAL_LINE_ENDING
        )

    logger.debug(f"Serial response: {return_value_with_line_ending}")

    return return_value_with_line_ending.decode("utf8").rstrip(
        _ALICAT_SERIAL_LINE_ENDING
    )


def _has_low_feed_pressure(alarm_str: str) -> bool:
    """ Given an alarm string from a mixer status, indicate whether low feed pressure is present
    """
    return bool(int(alarm_str) & _LOW_FEED_PRESSURE_ALARM_BIT)


def _ppb_to_fraction(ppb_str: str) -> float:
    """ Convert a parts per billion as a string (coming from MFC) to a fraction """
    return int(ppb_str) / _ONE_BILLION


def _fraction_to_ppb_str(fraction: float) -> str:
    """ Convert a fraction to a parts per billion number suitable for sending over serial """
    return str(int(fraction * _ONE_BILLION))


def _parse_flow_fraction(mfc_str: str) -> float:
    """ Fractions from the MFC come in parts per billion
    However, if there is a communication error or, more likely, the mixer hasn't been run since restart,
    the value is all dashes - interpret that as zero silently since it's not really an error.
    """
    if all(character == "-" for character in mfc_str):
        return 0
    return _ppb_to_fraction(mfc_str)


def _assert_expected_units(mixer_status_response: MixerStatusResponse) -> None:
    """ Make sure that pressure and flow units configured on the mixer correspond to mmHg and SLPM, respectively
    to prevent misinterpretation of results.
    """
    pressure_unit = int(mixer_status_response.pressure_units)
    flow_unit = int(mixer_status_response.flow_units)

    actual_pressure_and_flow_units = pressure_unit, flow_unit
    expected_pressure_and_flow_units = _PRESSURE_UNIT_CODE_MMHG, _FLOW_UNIT_CODE_SLPM

    if actual_pressure_and_flow_units != expected_pressure_and_flow_units:
        raise UnexpectedMixerResponse(
            f"Pressure and flow unit codes {actual_pressure_and_flow_units} "
            f"are not as expected {expected_pressure_and_flow_units}. "
            "Please check that mixer is set to our favorite "
            "units (mmHg for pressure and SLPM for flow)"
        )


def _parse_mixer_status(mixer_status_str: str) -> pd.Series:
    """ Parse a mixer status string returned from a QMXS ("query mixer status") command """
    mixer_status_values = mixer_status_str.split()
    mixer_status_response = MixerStatusResponse(*mixer_status_values)

    _assert_expected_units(mixer_status_response)
    try:
        return pd.Series(
            {
                "flow rate (SLPM)": float(mixer_status_response.mix_flow),
                "mix pressure (mmHg)": float(mixer_status_response.mix_pressure),
                "low feed pressure alarm": _has_low_feed_pressure(
                    mixer_status_response.mix_alarm
                ),
                "low feed pressure alarm - N2": _has_low_feed_pressure(
                    mixer_status_response.n2_status
                ),
                "low feed pressure alarm - O2 source gas": _has_low_feed_pressure(
                    mixer_status_response.o2_source_gas_status
                ),
                "N2 fraction in mix": _parse_flow_fraction(
                    mixer_status_response.n2_total_fraction
                ),
                "O2 source gas fraction in mix": _parse_flow_fraction(
                    mixer_status_response.o2_source_gas_total_fraction
                ),
            }
        )
    except ValueError as e:
        raise UnexpectedMixerResponse(
            f"Could not parse response. Response was:\n {MixerStatusResponse}\n. Error: {str(e)}"
        )


def _send_sequence_with_expected_responses(
    port: str, command_strs_and_expected_responses: List[Tuple[str, str]]
) -> None:
    """ Send a sequence of serial commands, checking that each response is exactly what is expected
    """
    for command, expected_response in command_strs_and_expected_responses:
        response = send_serial_command_str_and_get_response(command, port)
        if response != expected_response:
            raise UnexpectedMixerResponse(
                f'Expected mixer response to "{command}" was "{expected_response}" but we got "{response}"'
            )


def get_mixer_status(port: str) -> pd.Series:
    """ Query mixer status and provide return data helpful for calibration monitoring

    Args:
        port: serial port to connect to, e.g. COM19 on Windows and /dev/ttyUSB0 on linux

    Returns:
        pd.Series of useful stuff. Index includes:
            flow rate (SLPM): total flow rate out of mixer,
            mix pressure (mmHg): output pressure measured at mixer,
            low feed pressure alarm: whether any,
            low feed pressure alarm - N2: feed pressure alarm specific to N2 input,
            low feed pressure alarm - O2 source gas: feed pressure alarm specific to O2 source gas input,
            N2 fraction in mix: actual fraction of the N2 source gas, in the mix.
                NOTE that this is not necessarily the fractional volume of nitrogen in the result, since
                the O2 source gas may contain nitrogen as well.
            O2 source gas fraction in mix: 1,
                NOTE that this is not necessarily the fractional volume of O2 in the result, since
                the O2 source gas may not be pure oxygen if we are using a premixed source gas.

    """
    # mnemonic: QMXS = "query mixer status"
    command = f"{_DEVICE_ID} QMXS"
    response = send_serial_command_str_and_get_response(command, port)

    if not response:
        raise UnexpectedMixerResponse(
            f'No response to "{command}" command. Mixer may be disconnected or timeout too short'
        )

    return _parse_mixer_status(response)


def _parse_gas_ids(gas_id_response: str) -> pd.Series:
    """ Gas ID response is something like "A 1 4" where 1 and 4 are the respective gas IDs on the 2 MFCs. """
    gas_ids = gas_id_response.split()[1:]
    n2_gas_id, o2_gas_id = map(int, gas_ids)

    return pd.Series({"N2": n2_gas_id, "O2 source gas": o2_gas_id})


def get_gas_ids(port: str) -> pd.Series:
    """ Get IDs of gases on each port.
    These are not human readable but will allow us to tell when the source gases change -
    if the mixer is configured with a new, slightly different gas mix, that will get a new number.

    Args:
        port: Serial port the mix controller is attached to

    Returns:
        pandas Series of gas IDs: pd.Series({
            'N2': n2 gas ID,
            'O2 source gas': o2 source gas ID
        })
    """

    command = f"{_DEVICE_ID} MXFG"
    response = send_serial_command_str_and_get_response(command, port)

    if not response:
        raise UnexpectedMixerResponse(
            f'No response to "{command}" command. Mixer may be disconnected or timeout too short'
        )

    return _parse_gas_ids(response)


def _assert_valid_mix(flow_rate_slpm: float, o2_source_gas_fraction: float) -> None:
    """ Check that a given mix is possible on our mixer, raising ValueError if not.
    Raises:
        ValueError if the target flow rate and fraction are not achievable by the mixer configuration.
    """
    o2_source_gas_max_flow = 2.5
    n2_max_flow = 10
    o2_source_gas_target = flow_rate_slpm * o2_source_gas_fraction
    n2_target = flow_rate_slpm - o2_source_gas_target

    invalid_mix_message = (
        f"Invalid mix: flow rate {flow_rate_slpm} SLPM, "
        f"O2 source gas fraction {o2_source_gas_fraction}. "
    )

    o2_source_gas_error = (
        (
            "O2 source gas mixer only goes up to "
            f"{o2_source_gas_max_flow} but {o2_source_gas_target} is required for desired mix. "
        )
        if o2_source_gas_target > o2_source_gas_max_flow
        else ""
    )

    n2_error = (
        (
            f"N2 source gas mixer only goes up to "
            f"{n2_max_flow} but {n2_target} is required for desired mix. "
        )
        if n2_target > n2_max_flow
        else ""
    )

    if o2_source_gas_error or n2_error:
        raise ValueError(f"{invalid_mix_message}{o2_source_gas_error}{n2_error}")


def _get_o2_source_gas_fraction(target_o2_fraction, o2_source_gas_o2_fraction):
    if target_o2_fraction > o2_source_gas_o2_fraction:
        raise ValueError(
            f"Cannot achieve O2 fraction of {target_o2_fraction} "
            f"with source gas containing only {o2_source_gas_o2_fraction:.1%} O2"
        )
    return target_o2_fraction / o2_source_gas_o2_fraction


def start_constant_flow_mix(
    port: str,
    target_flow_rate_slpm: float,
    target_o2_fraction: float,
    o2_source_gas_o2_fraction: float = 1,
) -> None:
    """ Commands mixer to start a constant flow rate mix
    This also resets any alarms.

    Args:
        port: serial port to connect to.
        target_flow_rate_slpm: target flow rate, in SLPM
        target_o2_fraction: fraction of O2 in the desired mix. Note that if the connected O2
            source gas is not pure oxygen, this is not equivalent to the fraction of the O2 source gas in the final mix.
        o2_source_gas_o2_fraction: Fraction of O2 in the source gas connected to mixer 2. Defaults to 1.
            Used to calculate how much of the O2 source gas is required to hit the target O2 fraction.

    Returns:
        None

    Raises:
        UnexpectedMixerResponse if any mixer response is unexpected. There are currently no known causes for this.
        ValueError if the target flow rate and fraction are not achievable by the mixer configuration.
    """
    target_o2_source_gas_fraction = _get_o2_source_gas_fraction(
        target_o2_fraction, o2_source_gas_o2_fraction
    )
    n2_fraction = 1 - target_o2_source_gas_fraction
    n2_ppb = _fraction_to_ppb_str(n2_fraction)
    o2_source_gas_ppb = _fraction_to_ppb_str(target_o2_source_gas_fraction)
    min_mfc_flow_rate = 2.5  # flow rate of our smallest MFC
    _assert_valid_mix(target_flow_rate_slpm, target_o2_source_gas_fraction)

    commands_and_expected_responses = [
        (f"{_DEVICE_ID} MXRM 3", "A 3"),  # Set mixer run mode to constant flow
        (  # Initially set flow rate to a small number to make sure the fraction goes through.
            f"{_DEVICE_ID} MXRFF {min_mfc_flow_rate}",
            f"{_DEVICE_ID} {min_mfc_flow_rate:.2f} {_FLOW_UNIT_CODE_SLPM} SLPM",
        ),
        (  # Set target fraction.
            f"{_DEVICE_ID} MXMF {n2_ppb}, {o2_source_gas_ppb}",
            f"{_DEVICE_ID} {n2_ppb} {o2_source_gas_ppb}",
        ),
        (  # Set desired flow rate
            f"{_DEVICE_ID} MXRFF {target_flow_rate_slpm}",
            f"{_DEVICE_ID} {target_flow_rate_slpm:.2f} {_FLOW_UNIT_CODE_SLPM} SLPM",
        ),
        (f"{_DEVICE_ID} MXRS 1", f"{_DEVICE_ID} 2"),  # mixer run state: Start mixin'
    ]

    _send_sequence_with_expected_responses(port, commands_and_expected_responses)


def stop_flow(port: str) -> None:
    """ Stop flow on the gas mixer.

    Args:
        port: serial port that gas mixer is connected on

    Returns:
        None

    Raises:
        UnexpectedMixerResponse if the mixer is anything other than stopped with no alarms after this command.
            Likely cause is that the mixer was already stopped due to an alarm.
    """
    # mnemonic: "MXRS" = "mixer run state"
    command = f"{_DEVICE_ID} MXRS 2"
    response = send_serial_command_str_and_get_response(command, port)
    _assert_mixer_state(response, _MixControllerStateCode.stopped_ok)
