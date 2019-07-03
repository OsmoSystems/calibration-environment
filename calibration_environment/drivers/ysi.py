from enum import Enum

import pandas as pd

from calibration_environment.drivers.serial_port import (
    send_serial_command_and_get_response,
)


class YSICommand(str, Enum):
    get_barometric_pressure_mmhg = "Get Normal SENSOR_BAR_MMHG"
    get_barometric_pressure_kpa = "Get Normal SENSOR_BAR_KPA"
    get_do_pct_sat = "Get Normal SENSOR_DO_PERCENT_SAT"
    get_do_mg_l = "Get Normal SENSOR_DO_MG_L"
    get_temp_c = "Get Normal SENSOR_TEMP_C"

    def to_bytes_packet(self) -> bytes:
        return bytes(f"$ADC {self.value}\r\n", encoding="utf8")


YSI_RESPONSE_TERMINATOR = b"\r\n$ACK\r\n"


def parse_ysi_response(response_str):
    """ Response format is something like "$49.9..$ACK.." for 49.9
    """
    return float(response_str[1 : -len(YSI_RESPONSE_TERMINATOR)])


def get_sensor_value(port: str, command: YSICommand) -> str:
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
        response_terminator=YSI_RESPONSE_TERMINATOR,
        baud_rate=57600,
        timeout=1,
    )

    return parse_ysi_response(response_bytes.decode("utf8"))


def get_standard_sensor_values(port):
    """ Get a standard complement of sensor values from a YSI sensor in our standard units. """
    return pd.Series(
        {
            "Barometric pressure (mmHg)": get_sensor_value(
                port, YSICommand.get_barometric_pressure_mmhg
            ),
            "DO (% sat)": get_sensor_value(port, YSICommand.get_do_pct_sat),
            "Temperature (C)": get_sensor_value(port, YSICommand.get_temp_c),
        }
    )
