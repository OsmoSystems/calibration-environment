# Commands to get the status of the NESLAB RTE 17 temperature-controlled water bath & verify that it's OK
import collections

from calibration_environment.drivers.water_bath.constants import READ_STATUS_COMMAND
from calibration_environment.drivers.water_bath.exceptions import WaterBathStatusError
from calibration_environment.drivers.water_bath.serial import SerialPacket, send_command


WaterBathStatus = collections.namedtuple(
    "WaterBathStatus",
    [
        # Each of these is either True or False
        # Names and ordering are from the manual:
        # https://drive.google.com/file/d/1Tg-e1C8Ht8BE7AYzKVSqjw9bhWWxqKlz/edit?disco=AAAADTMD4oQ
        # Byte 1:
        "rtd1_open_fault",
        "rtd1_shorted_fault",
        "rtd1_open",
        "rtd1_shorted",
        "rtd3_open_fault",
        "rtd3_shorted_fault",
        "rtd3_open",
        "rtd3_shorted",
        # Byte 2:
        "rtd2_open_fault",
        "rtd2_shorted_fault",
        "rtd2_open_warn",
        "rtd2_shorted_warn",
        "rtd2_open",
        "rtd2_shorted",
        "refrig_high_temp",
        "htc_fault",
        # Byte 3:
        "high_fixed_temp_fault",
        "low_fixed_temp_fault",
        "high_temp_fault",
        "low_temp_fault",
        "low_level_fault",
        "high_temp_warn",
        "low_temp_warn",
        "low_level_warn",
        # Byte 4:
        "buzzer_on",
        "alarm_muted",
        "unit_faulted",
        "unit_stopping",
        "unit_on",
        "pump_on",
        "compressor_on",
        "heater_on",
        # Byte 5:
        "rtd2_controlling",
        # note: if an LED is flashing, it will also be marked as ON
        "heat_led_flashing",
        "heat_led_on",
        "cool_led_flashing",
        "cool_led_on",
        # # The Status response contains 3 unused bits
        # "Unused 1",
        # "Unused 2",
        # "Unused 3",
    ],
)

_UNUSED_SETTINGS_DATA_BITS_COUNT = 3


def _parse_status_data_bytes(status_response_bytes: bytes) -> WaterBathStatus:
    """ Parse data_bytes from the bath's response to a "Set On/Off Array" command
    """
    status_bits = [
        bool(int(bit_char))  # each "1" or "0" char to a number then a boolean
        for byte in status_response_bytes
        for bit_char in "{0:08b}".format(byte)  # "{0:08b}" formats like "00101011"
    ]
    return WaterBathStatus(*status_bits[:-_UNUSED_SETTINGS_DATA_BITS_COUNT])


def get_water_bath_status(port: str) -> WaterBathStatus:
    """ Get an up-to-date WaterBathStatus

        Args:
            port: the comm port used by the water bath

        Returns:
            The response from the water bath as an WaterBathStatus tuple
        """
    response_packet = send_command(port, SerialPacket.from_command(READ_STATUS_COMMAND))

    return _parse_status_data_bytes(response_packet.data_bytes)


_ERROR_MARKERS = ["fault", "warn", "shorted", "refrig_high_temp"]


def _is_error_key(status_key: str):
    """ given a field name from WaterBathStatus, indicate whether it is something to worry about when it goes high """
    return any(error_marker in status_key for error_marker in _ERROR_MARKERS)


def _validate_status(status: WaterBathStatus) -> None:
    """
    Args:
        status: WaterBathStatus
    Returns:
        None
    Raises:
        WaterBathStatusError with a list of error or warning flags raised in the water bath's status registers
    """

    errors = [
        status_key
        for status_key, status_value in status._asdict().items()
        if _is_error_key(status_key) and status_value
    ]
    if errors:
        raise WaterBathStatusError(errors)


def assert_status_ok(port: str) -> None:
    """ Ensure that the water bath has no error statuses

        Args:
            port: The comm port used by the water bath
        Raises:
            WaterBathStatusError if the water bath has a warning or fault status of any kind
    """
    status = get_water_bath_status(port)

    _validate_status(status)
