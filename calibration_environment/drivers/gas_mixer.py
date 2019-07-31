import logging
import re
from collections import namedtuple
from enum import IntEnum
from typing import Tuple, List

import pandas as pd

from calibration_environment.drivers.serial_port import (
    send_serial_command_and_get_response,
)
from calibration_environment.retry import retry_on_exception

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
_ALICAT_SERIAL_TERMINATOR_BYTE = b"\r"

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

# Expected unit settings
_PRESSURE_UNIT_CODE_MMHG = 14
_FLOW_UNIT_CODE_SLPM = 7

# Maximum flow rates on our MFCs, SLPM
_N2_MAX_FLOW = 10
_O2_SOURCE_GAS_MAX_FLOW = 2.5

# In status fields, this bit is used to indicate low feed pressure,
# which generally means a cylinder is exhausted, not connected or there's a kink in the line
_LOW_FEED_PRESSURE_ALARM_BIT = 0x008000

_ONE_BILLION = 1000000000

# According to Alicat we shouldn't run the MFCs lower than 1-2% of their full flow rate
# to prevent the risk of the mixture being out of spec / taking longer to equilibrate
# Use 2% to err on the safe side
MIN_FLOW_RATE_FRACTION = 0.02


class _MixControllerStateCode(IntEnum):
    """ Codes returned by the mix controller in response to a mixer status (MXRS) command or query """

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


class _MixControllerRunStateRequestCode(IntEnum):
    """ Codes used to command the mix controller in a mixer status (MXRS) command """

    clear_alarms_and_start_mixing = 1
    stop_flow = 2
    clear_alarms = 3
    quiet_alarms = 4
    enter_service_mode = 5

    @property
    def description(self):
        return {
            1: "Clear any existing alarms, exit service mode, and start mixing.",
            2: "Stop flow. If in service mode, exit service mode and stop flow. Any existing alarms remain active.",
            3: "Clear any existing alarms. Mixing remains stopped.",
            4: "Quiet any existing alarm but do not clear any alarms.",
            5: "Enter service mode. The mix module suspends all communication with the MFCs, "
            "but any existing alarms remain active.",
        }[self]

    def __str__(self):
        return f'MixControllerRunStateRequestCode #{self.value}: "{self.description}"'


_MIXER_MODE_CODE_CONSTANT_FLOW = 3


class UnexpectedMixerResponse(Exception):
    # General error for when the mixer doesn't tell us what we expect it to.
    pass


def _assert_mixer_state(
    actual_response: str, expected_codes: List[_MixControllerStateCode]
) -> None:

    # Response will look something like "A 3" where "3" is the code
    regex = r"{device_id} (\d)".format(device_id=_DEVICE_ID)
    match = re.match(regex, actual_response)
    actual_code = _MixControllerStateCode(
        int(
            match.groups()[0]  # type: ignore # mypy issue with groups()
        )
    )

    if actual_code not in expected_codes:
        raise UnexpectedMixerResponse(
            f"Expected one of {expected_codes!s} but received {actual_code!s}"
        )


def send_serial_command_str_and_parse_response(command_str: str, port: str) -> str:
    """ Given a serial command, send it on a serial port and return the response.
    Handles Alicat default serial settings and line endings.

    Args:
        command_str: str of command to send, without termination character
        port: serial port to connect to, e.g. COM19 on Windows and /dev/ttyUSB0 on linux

    Returns:
        response, as a string with the alicat end-of-line character (carriage return) stripped
    """

    # Add the expected line ending and convert to bytes for serial transmission
    command_bytes = bytes(command_str, encoding="utf8") + _ALICAT_SERIAL_TERMINATOR_BYTE

    response_bytes = send_serial_command_and_get_response(
        port=port,
        command=command_bytes,
        baud_rate=_ALICAT_BAUD_RATE,
        response_terminator=_ALICAT_SERIAL_TERMINATOR_BYTE,
        timeout=1,
    )

    if not response_bytes.endswith(_ALICAT_SERIAL_TERMINATOR_BYTE):
        raise UnexpectedMixerResponse(
            f'Mixer response "{response_bytes.decode("utf8")}" did not end with '
            f'alicat serial terminator "{_ALICAT_SERIAL_TERMINATOR_BYTE.decode("utf8")}".'
        )

    return response_bytes.rstrip(_ALICAT_SERIAL_TERMINATOR_BYTE).decode("utf8")


def _has_low_feed_pressure(alarm_str: str) -> bool:
    """ Given an alarm string from a mixer status, indicate whether low feed pressure is present
    """
    return bool(int(alarm_str) & _LOW_FEED_PRESSURE_ALARM_BIT)


def _ppb_to_fraction(ppb_value: int) -> float:
    """ Convert a parts per billion as a string (coming from MFC) to a fraction """
    return ppb_value / _ONE_BILLION


def _fraction_to_ppb(fraction: float) -> int:
    """ Convert a fraction to a parts per billion number suitable for sending over serial """
    return int(fraction * _ONE_BILLION)


def _complimentary_ppb_value(ppb_value: int) -> int:
    """ Get the complimentary parts-per-billion value that with this ppb value, adds up to one billion.
    The gas mixer cares that ppb fractions add up to exactly one billion
    So, use this instead of converting numbers to ppb individually.
    """
    return _ONE_BILLION - int(ppb_value)


def _parse_flow_fraction(mfc_str: str) -> float:
    """ Fractions from the MFC come in parts per billion
    However, if there is a communication error or, more likely, the mixer hasn't been run since restart,
    the value is all dashes - interpret that as zero silently since it's not really an error.
    """
    if all(character == "-" for character in mfc_str):
        return 0
    return _ppb_to_fraction(int(mfc_str))


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
    if len(mixer_status_values) != len(MixerStatusResponse._fields):
        raise UnexpectedMixerResponse(
            f'Mixer response "{mixer_status_str}" contained {len(mixer_status_values)} '
            f"fields instead of the expected {len(MixerStatusResponse._fields)}."
        )

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
            f"Could not parse response. Response was:\n {mixer_status_response}\n. Error: {str(e)}"
        )


def _send_sequence_with_expected_responses(
    port: str, command_strs_and_expected_responses: List[Tuple[str, str]]
) -> None:
    """ Send a sequence of serial commands, checking that each response is exactly what is expected
    """
    for command, expected_response in command_strs_and_expected_responses:
        response = send_serial_command_str_and_parse_response(command, port)
        if response != expected_response:
            raise UnexpectedMixerResponse(
                f'Expected mixer response to "{command}" was "{expected_response}" but we got "{response}"'
            )


def _get_mixer_status(port: str) -> pd.Series:
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
            N2 fraction in mix: Fraction of the mix that comes from the N2 source gas canister.
                NOTE that this is not necessarily the fractional volume of nitrogen in the result, since
                the O2 source gas may contain nitrogen as well.
            O2 source gas fraction in mix: Fraction of the mix that comes from
                the O2 source gas (the canister containing oxygen)
                NOTE that this is not necessarily the fractional volume of O2 in the result, since
                the O2 source gas may not be pure oxygen if we are using a premixed source gas.

    """
    # mnemonic: QMXS = "query mixer status"
    command = f"{_DEVICE_ID} QMXS"
    response = send_serial_command_str_and_parse_response(command, port)

    if not response:
        raise UnexpectedMixerResponse(
            f'No response to "{command}" command. Mixer may be disconnected or timeout too short'
        )

    return _parse_mixer_status(response)


get_mixer_status_with_retry = retry_on_exception(UnexpectedMixerResponse)(
    _get_mixer_status
)


def _parse_gas_ids(gas_id_response: str) -> pd.Series:
    """ Gas ID response is something like "A 1 4" where 1 and 4 are the respective gas IDs on the 2 MFCs. """
    gas_ids = gas_id_response.split()[1:]
    n2_gas_id, o2_gas_id = map(int, gas_ids)

    return pd.Series({"N2": n2_gas_id, "O2 source gas": o2_gas_id})


def _get_gas_ids(port: str) -> pd.Series:
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
    # mnemonic: "MXFG" = "mixer feed gases"
    command = f"{_DEVICE_ID} MXFG"
    response = send_serial_command_str_and_parse_response(command, port)

    if not response:
        raise UnexpectedMixerResponse(
            f'No response to "{command}" command. Mixer may be disconnected or timeout too short'
        )

    return _parse_gas_ids(response)


get_gas_ids_with_retry = retry_on_exception(UnexpectedMixerResponse)(_get_gas_ids)


def get_mix_validation_errors(
    total_flow_rate_slpm: float,
    o2_source_gas_o2_fraction: float,
    setpoint_o2_fraction: float,
) -> List:
    """ Validate that a given mix is possible on our mixer.
        Args:
            total_flow_rate_slpm: Total setpoint flow rate in SLPM.
            o2_source_gas_o2_fraction: O2 fraction of O2 source gas.
            setpoint_o2_fraction: Desired output gas O2 fraction.
        Returns:
            List containing validation errors in this mix.
    """
    o2_source_gas_flow_rate = _get_o2_source_gas_flow_rate(
        total_flow_rate_slpm, setpoint_o2_fraction, o2_source_gas_o2_fraction
    )
    n2_source_gas_flow_rate = total_flow_rate_slpm - o2_source_gas_flow_rate

    validation_errors = {
        # fmt: off
        "setpoint gas O2 fraction too high":
            setpoint_o2_fraction > o2_source_gas_o2_fraction,
        f"O2 flow rate > {_O2_SOURCE_GAS_MAX_FLOW} SLPM":
            o2_source_gas_flow_rate > _O2_SOURCE_GAS_MAX_FLOW,
        f"O2 flow rate < 2% of full scale ({_O2_SOURCE_GAS_MAX_FLOW * MIN_FLOW_RATE_FRACTION} SLPM)":
            o2_source_gas_flow_rate < _O2_SOURCE_GAS_MAX_FLOW * MIN_FLOW_RATE_FRACTION
            and o2_source_gas_flow_rate != 0,
        f"N2 flow rate > {_N2_MAX_FLOW} SLPM":
            n2_source_gas_flow_rate > _N2_MAX_FLOW,
        f"N2 flow rate < 2% of full scale ({_N2_MAX_FLOW * MIN_FLOW_RATE_FRACTION} SLPM)":
            n2_source_gas_flow_rate < _N2_MAX_FLOW * MIN_FLOW_RATE_FRACTION
            and n2_source_gas_flow_rate != 0,
        # fmt: on
    }

    return [error for error, present in validation_errors.items() if present]


def _get_o2_source_gas_flow_rate(
    total_flow_rate_slpm, setpoint_o2_fraction, o2_source_gas_o2_fraction
):
    return total_flow_rate_slpm * setpoint_o2_fraction / o2_source_gas_o2_fraction


def _get_source_gas_flow_rates_ppb(
    o2_source_gas_o2_fraction: float, setpoint_o2_fraction: float
) -> Tuple[int, int]:
    """ Calculate how much of each source gas, in ppb, is required to hit a setpoint O2 fraction

        Args:
            o2_source_gas_o2_fraction: Fraction of O2 in the source gas connected to mixer 2. Defaults to 1.
            setpoint_o2_fraction: fraction of O2 in the desired mix

        Returns:
            n2_ppb, o2_source_gas_ppb: tuple of integer PPM values
    """
    setpoint_o2_source_gas_fraction = setpoint_o2_fraction / o2_source_gas_o2_fraction
    o2_source_gas_ppb = _fraction_to_ppb(setpoint_o2_source_gas_fraction)
    n2_ppb = _complimentary_ppb_value(o2_source_gas_ppb)
    return n2_ppb, o2_source_gas_ppb


def _stop_flow(port: str) -> None:
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
    command = f"{_DEVICE_ID} MXRS {_MixControllerRunStateRequestCode.stop_flow.value}"
    response = send_serial_command_str_and_parse_response(command, port)
    _assert_mixer_state(
        response,
        # Any type of "stopped" is OK.
        [
            _MixControllerStateCode.stopped_ok,
            _MixControllerStateCode.stopped_error,
            _MixControllerStateCode.stopped_configuration_error,
            _MixControllerStateCode.stopped_error_silent,
        ],
    )


stop_flow_with_retry = retry_on_exception(UnexpectedMixerResponse)(_stop_flow)


def _start_constant_flow_mix(
    port: str,
    setpoint_flow_rate_slpm: float,
    setpoint_o2_fraction: float,
    o2_source_gas_o2_fraction: float = 1,
) -> None:
    """ Commands mixer to start a constant flow rate mix
    This also resets any alarms.

    Args:
        port: serial port to connect to.
        setpoint_flow_rate_slpm: setpoint flow rate, in SLPM
        setpoint_o2_fraction: fraction of O2 in the desired mix. Note that if the connected O2
            source gas is not pure oxygen, this is not equivalent to the fraction of the O2 source gas in the final mix.
        o2_source_gas_o2_fraction: Fraction of O2 in the source gas connected to mixer 2. Defaults to 1.
            Used to calculate how much of the O2 source gas is required to hit the setpoint O2 fraction.

    Returns:
        None

    Raises:
        UnexpectedMixerResponse if any mixer response is unexpected. There are currently no known causes for this.
        ValueError if the setpoint flow rate and fraction are not achievable by the mixer configuration.
    """
    if setpoint_flow_rate_slpm == 0:
        # MFC controller does not allow you to "start a flow" with a rate of zero. So we just turn it off and head home
        _stop_flow(port)
        return

    validation_errors = get_mix_validation_errors(
        setpoint_flow_rate_slpm, o2_source_gas_o2_fraction, setpoint_o2_fraction
    )
    if validation_errors:
        errors_string = ", ".join(validation_errors)
        raise ValueError(
            (
                f"Invalid flow mix: {setpoint_o2_fraction} setpoint O2 fraction at {setpoint_flow_rate_slpm} SLPM "
                f"with {o2_source_gas_o2_fraction} source O2 fraction\n"
                f"Errors: {errors_string}"
            )
        )

    n2_ppb, o2_source_gas_ppb = _get_source_gas_flow_rates_ppb(
        o2_source_gas_o2_fraction, setpoint_o2_fraction
    )

    commands_and_expected_responses = [
        (  # Set mixer run mode to constant flow
            f"{_DEVICE_ID} MXRM {_MIXER_MODE_CODE_CONSTANT_FLOW}",
            f"A {_MIXER_MODE_CODE_CONSTANT_FLOW}",
        ),
        (  # Set target fraction.
            # NOTE: it is important to set the fraction before the flow rate,
            # since the mix controller will automatically reset the flow rate to something that works based on the
            # fraction (thus rejecting our setpoint if we set the flow rate first),
            # but not vice versa (fraction first is always respected if possible).
            f"{_DEVICE_ID} MXMF {n2_ppb} {o2_source_gas_ppb}",
            f"{_DEVICE_ID} {n2_ppb} {o2_source_gas_ppb}",
        ),
        (  # Set desired flow rate
            f"{_DEVICE_ID} MXRFF {setpoint_flow_rate_slpm:.2f}",
            f"{_DEVICE_ID} {setpoint_flow_rate_slpm:.2f} {_FLOW_UNIT_CODE_SLPM} SLPM",
        ),
        (  # mixer run state: Start mixin'
            f"{_DEVICE_ID} MXRS {_MixControllerRunStateRequestCode.clear_alarms_and_start_mixing.value}",
            f"{_DEVICE_ID} {_MixControllerStateCode.mixing.value}",
        ),
    ]

    _send_sequence_with_expected_responses(port, commands_and_expected_responses)


start_constant_flow_mix_with_retry = retry_on_exception(UnexpectedMixerResponse)(
    _start_constant_flow_mix
)
