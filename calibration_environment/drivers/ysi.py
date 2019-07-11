from enum import Enum

import pandas as pd

from calibration_environment.drivers.serial_port import (
    send_serial_command_and_get_response,
)


class InvalidYsiResponse(Exception):
    pass


class YSICommand(str, Enum):
    get_barometric_pressure_mmhg = "Get Normal SENSOR_BAR_MMHG"
    get_barometric_pressure_kpa = "Get Normal SENSOR_BAR_KPA"
    get_do_pct_sat = "Get Normal SENSOR_DO_PERCENT_SAT"
    get_do_mg_l = "Get Normal SENSOR_DO_MG_L"
    get_temp_c = "Get Normal SENSOR_TEMP_C"

    def to_bytes_packet(self) -> bytes:
        return bytes(f"$ADC {self.value}\r\n", encoding="utf8")


_YSI_RESPONSE_TERMINATOR = b"\r\n$ACK\r\n"
_YSI_RESPONSE_INITIATOR = b"$"
_YSI_BAUD_RATE = 57600


def parse_ysi_response(response_bytes: bytes):
    """ Response format is something like "$49.9\r\n$ACK\r\n" for 49.9
    """
    if not response_bytes.endswith(_YSI_RESPONSE_TERMINATOR):
        raise InvalidYsiResponse(
            f"{response_bytes} is missing the expected YSI response terminator {_YSI_RESPONSE_TERMINATOR}"
        )

    if not response_bytes.startswith(_YSI_RESPONSE_INITIATOR):
        raise InvalidYsiResponse(
            f"{response_bytes} is missing the expected YSI response initiator {_YSI_RESPONSE_INITIATOR}"
        )

    response_substr = response_bytes.decode("utf8")[
        len(_YSI_RESPONSE_INITIATOR) : -len(_YSI_RESPONSE_TERMINATOR)
    ]

    try:
        return float(response_substr)
    except ValueError:
        raise InvalidYsiResponse(
            f'"{response_substr}" from within YSI response {response_bytes} could not be converted to a float'
        )


def get_sensor_reading(port: str, command: YSICommand) -> str:
    """ Given a serial command, send it on a serial port and return the response.
    Handles YSI default serial settings and stuff.

    Args:
        command: YSICommand to send
        port: serial port to connect to, e.g. COM11 on Windows and /dev/ttyUSB0 on linux

    Returns:
        response, as a floating-point value
    """

    response_bytes = send_serial_command_and_get_response(
        port=port,
        command=command.to_bytes_packet(),
        response_terminator=_YSI_RESPONSE_TERMINATOR,
        baud_rate=_YSI_BAUD_RATE,
        timeout=1,
    )

    return parse_ysi_response(response_bytes)


def get_standard_sensor_values(port):
    """ Get a standard complement of sensor values from a YSI sensor in our standard units. """
    return pd.Series(
        {
            "barometric pressure (mmHg)": get_sensor_reading(
                port, YSICommand.get_barometric_pressure_mmhg
            ),
            "DO (mg/L)": get_sensor_reading(port, YSICommand.get_do_mg_l),
            "DO (% sat)": get_sensor_reading(port, YSICommand.get_do_pct_sat),
            "temperature (C)": get_sensor_reading(port, YSICommand.get_temp_c),
        }
    )
