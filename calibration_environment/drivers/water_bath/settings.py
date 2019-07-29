# Commands to control the internal settings of the NESLAB RTE 17 temperature-controlled water bath
import collections

from calibration_environment.drivers.water_bath.constants import (
    SET_ON_OFF_ARRAY_COMMAND,
    ENABLE_HIGH_PRECISION,
    REPORTING_PRECISION,
)
from calibration_environment.drivers.water_bath.serial import SerialPacket, send_command


OnOffArraySettings = collections.namedtuple(
    "OnOffArraySettings",
    [
        # Each of these can be True (enable), False (disable) or None (don't change)
        "unit_on_off",  # Turn unit on/off. True: Turn it on. False: Turn it off
        "external_sensor_enable",  # True: Use external sensor. False: Use internal sensor
        "faults_enabled",  # Behavior when faults encountered. True: Shut down. False: Continue to run.
        "mute",
        "auto_restart",
        "high_precision_enable",  # Use 0.01 C precision. True: Use 0.01 C. False: Use 0.1 C.
        "full_range_cool_enable",
        "serial_comm_enable",  # Serial communication. True: Use serial communication. False: use local
    ],
)


def _construct_settings_command_packet(settings: OnOffArraySettings) -> SerialPacket:
    """ Construct a command packet to set on/off settings to desired, hardcoded values
    """
    setting_to_command_byte = {False: 0, True: 1, None: 2}
    data_bytes = bytes(setting_to_command_byte[setting] for setting in settings)
    return SerialPacket.from_command(
        command=SET_ON_OFF_ARRAY_COMMAND, data_bytes=data_bytes
    )


def _parse_settings_data_bytes(settings_data_bytes: bytes) -> OnOffArraySettings:
    """ Parse data_bytes from the bath's response to a "Set On/Off Array" command
    """
    return OnOffArraySettings(*settings_data_bytes)


def _validate_initialized_settings(settings: OnOffArraySettings):
    checks = {
        "Water bath isn't turned on": settings.unit_on_off,
        "Internal sensor isn't enabled": not settings.external_sensor_enable,
        f"Precision isn't {REPORTING_PRECISION}": (
            settings.high_precision_enable == ENABLE_HIGH_PRECISION
        ),
        "Serial comms aren't enabled": settings.serial_comm_enable,
    }

    errors = [error_message for error_message, check in checks.items() if not check]
    if errors:
        raise ValueError(errors)


def send_settings_command_and_parse_response(
    port: str,
    unit_on_off: bool = None,
    external_sensor_enable: bool = None,
    faults_enabled: bool = None,
    mute: bool = None,
    auto_restart: bool = None,
    high_precision_enable: bool = None,
    full_range_cool_enable: bool = None,
    serial_comm_enable: bool = None,
) -> OnOffArraySettings:
    """ Send a settings command to the water bath and parse the response data.

        The "Set On/Off Array" command has a unique data structure in which each data byte
        represents a single setting that can be toggled (including turning on/off the bath).

        Data bytes meaning:
            (di: 0 = off, 1 = on, 2 = no change)
            d1 = unit on/off
            d2 = sensor enable
            d3 = faults enabled
            d4 = mute
            d5 = auto restart
            d6 = 0.01°C enable
            d7 = full range cool enable
            d8 = serial comm enable

        Args:
            port: the comm port used by the water bath
            unit_on_off: if provided, turn unit on (True) or off (False)
            external_sensor_enable: if provided, determine whether the internal (False) or external (True) probe is
                used for temperature feedback
            faults_enabled: if provided, set behavior when faults encountered. True: shut down. False: continue to run.
            mute: if provided, mute audible alarms (True) or unmute (False)
            auto_restart: if provided, control auto restart setting
            high_precision_enable: if provided, set control precision. True: Use 0.01 C. False: Use 0.1 C.
            full_range_cool_enable: if provided, enable (True) / disable (False) full range cooling
            serial_comm_enable: if provided, set serial communications status.
                True: Use serial communication. False: use local (buttons)

        Returns:
            The response from the water bath as an OnOffArraySettings tuple
        """
    settings = OnOffArraySettings(
        unit_on_off=unit_on_off,
        external_sensor_enable=external_sensor_enable,
        faults_enabled=faults_enabled,
        mute=mute,
        auto_restart=auto_restart,
        high_precision_enable=high_precision_enable,
        full_range_cool_enable=full_range_cool_enable,
        serial_comm_enable=serial_comm_enable,
    )
    settings_command_packet = _construct_settings_command_packet(settings)
    response_packet = send_command(port, settings_command_packet)

    return _parse_settings_data_bytes(response_packet.data_bytes)


def initialize(port: str) -> OnOffArraySettings:
    """ Ensure that the water bath is turned on and that its settings are initialized
        as we expect by sending a set settings command.

        Args:
            port: The comm port used by the water bath
    """
    response_settings = send_settings_command_and_parse_response(
        port,
        # Turn it on...
        unit_on_off=True,
        # Use internal temperature sensor
        external_sensor_enable=False,
        # Assert high precision
        high_precision_enable=ENABLE_HIGH_PRECISION,
        # Note: we'd like to make sure that serial communications are enabled,
        # but they have to be enabled already or else this won't work :p
        serial_comm_enable=None,
    )

    _validate_initialized_settings(response_settings)

    return response_settings
