from .serial import send_command_and_parse_response  # noqa: F401 unused imports
from .setpoint import get_temperature_validation_errors  # noqa: F401 unused imports
from .settings import (  # noqa: F401 unused imports
    OnOffArraySettings,
    send_settings_command_and_parse_response,
    initialize,
)

"""
A driver for the Thermo Scientific NESLAB RTE 17 Temperature-controlled water bath

Excerpts from the datasheet:
(https://drive.google.com/file/d/1Tg-e1C8Ht8BE7AYzKVSqjw9bhWWxqKlz?disco=AAAADMVYeIw)

"""
