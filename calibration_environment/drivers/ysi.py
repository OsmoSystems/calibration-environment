from enum import Enum
from typing import Callable
from urllib.parse import unquote

import pandas as pd

from calibration_environment.drivers.serial_port import (
    send_serial_command_and_get_response,
)
from calibration_environment.retry import retry_on_exception


class InvalidYsiResponse(Exception):
    pass


class YSICommand(Enum):
    get_barometric_pressure_mmhg = "Get Normal SENSOR_BAR_MMHG"
    get_barometric_pressure_kpa = "Get Normal SENSOR_BAR_KPA"
    get_do_pct_sat = "Get Normal SENSOR_DO_PERCENT_SAT"
    get_do_mg_l = "Get Normal SENSOR_DO_MG_L"
    get_temp_c = "Get Normal SENSOR_TEMP_C"
    get_unit_id = "Get UnitID"

    @property
    def command_prefix(self) -> str:
        """ Prefix used when packing this into a command packet """
        return "INFO" if self == YSICommand.get_unit_id else "ADC"

    @property
    def response_payload_parser(self):
        """ Method to parse the response payload (extracted form the response packet) into a clean object """
        return (
            unquote  # The response to Get UnitID is a urlencoded string (with %20 for spaces, for example)
            if self == YSICommand.get_unit_id
            else float
        )


_YSI_RESPONSE_TERMINATOR = b"\r\n$ACK\r\n"
_YSI_RESPONSE_INITIATOR = b"$"
_YSI_BAUD_RATE = 57600


def parse_response_packet(response_bytes: bytes, payload_parser: Callable):
    """ Response format is something like "$49.9\r\n$ACK\r\n" for 49.9
    """
    if not response_bytes.endswith(_YSI_RESPONSE_TERMINATOR):
        raise InvalidYsiResponse(
            f"{response_bytes!r} is missing the expected YSI response terminator {_YSI_RESPONSE_TERMINATOR!r}"
        )

    if not response_bytes.startswith(_YSI_RESPONSE_INITIATOR):
        raise InvalidYsiResponse(
            f"{response_bytes!r} is missing the expected YSI response initiator {_YSI_RESPONSE_INITIATOR!r}"
        )

    response_substr = response_bytes.decode("utf8")[
        len(_YSI_RESPONSE_INITIATOR) : -len(_YSI_RESPONSE_TERMINATOR)
    ]

    try:
        return payload_parser(response_substr)
    except ValueError:
        raise InvalidYsiResponse(
            f'"{response_substr!r}" from within YSI response {response_bytes!r} '
            f"could not be parsed using {payload_parser}"
        )


def _create_command_packet(command: YSICommand):
    return bytes(f"${command.command_prefix} {command.value}\r\n", encoding="utf8")


def _get_sensor_reading(port: str, command: YSICommand):
    """ Given a serial command, send it on a serial port and return the response.
    Handles YSI default serial settings and stuff.

    Args:
        command: YSICommand to send
        port: serial port to connect to, e.g. COM11 on Windows and /dev/ttyUSB0 on linux

    Returns:
        response, as the appropriate response type for the given command
    Raises:
        InvalidYsiResponse if response packet is invalid after retries
    """

    response_bytes = send_serial_command_and_get_response(
        port=port,
        command=_create_command_packet(command),
        response_terminator=_YSI_RESPONSE_TERMINATOR,
        baud_rate=_YSI_BAUD_RATE,
        timeout=1,
    )

    return parse_response_packet(
        response_bytes, payload_parser=command.response_payload_parser
    )


get_sensor_reading_with_retry = retry_on_exception(InvalidYsiResponse)(
    _get_sensor_reading
)


_ATMOSPHERIC_OXYGEN_FRACTION = 0.2095


def _calculate_partial_pressure(do_percent_saturation, barometric_pressure_mmhg):
    do_fraction_saturation = do_percent_saturation * 0.01
    return (
        do_fraction_saturation * _ATMOSPHERIC_OXYGEN_FRACTION * barometric_pressure_mmhg
    )


def get_standard_sensor_values(port):
    """ Get a standard complement of sensor values from a YSI sensor in our standard units. """

    do_percent_saturation = get_sensor_reading_with_retry(
        port, YSICommand.get_do_pct_sat
    )
    barometric_pressure_mmhg = get_sensor_reading_with_retry(
        port, YSICommand.get_barometric_pressure_mmhg
    )
    do_mmhg = _calculate_partial_pressure(
        do_percent_saturation, barometric_pressure_mmhg
    )

    return pd.Series(
        {
            "Unit ID": get_sensor_reading_with_retry(port, YSICommand.get_unit_id),
            "barometric pressure (mmHg)": barometric_pressure_mmhg,
            "DO (mg/L)": get_sensor_reading_with_retry(port, YSICommand.get_do_mg_l),
            "DO (% sat)": do_percent_saturation,
            "DO (mmHg)": do_mmhg,
            "temperature (C)": get_sensor_reading_with_retry(
                port, YSICommand.get_temp_c
            ),
        }
    )
