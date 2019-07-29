# Constants required for the NESLAB RTE 17 temperature-controlled water bath

# The bath can report data with either 0.1 or 0.01 precision. We want the high precision option
REPORTING_PRECISION = 0.01
ENABLE_HIGH_PRECISION = {0.01: True, 0.1: False}[REPORTING_PRECISION]

# Default protocol settings on the NESLAB RTE. They can be reconfigured.
DEFAULT_BAUD_RATE = 19200

# We're using RS-232, which means the prefix is 0xCA and the device address is
# always 0x00 0x01
DEFAULT_PREFIX = 0xCA
DEFAULT_DEVICE_ADDRESS_MSB = 0x00
DEFAULT_DEVICE_ADDRESS_LSB = 0x01

COMMAND_NAME_TO_HEX = {
    # Read Commands
    "Read Internal Temperature": 0x20,
    "Read External Sensor": 0x21,
    "Read Setpoint": 0x70,
    "Read Low Temperature Limit": 0x40,
    "Read High Temperature Limit": 0x60,
    "Read Heat Proportional Band": 0x71,
    "Read Heat Integral": 0x72,
    "Read Heat Derivative": 0x73,
    "Read Cool Proportional Band": 0x74,
    "Read Cool Integral": 0x75,
    "Read Cool Derivative": 0x76,
    # Set Commands
    "Set Setpoint": 0xF0,  # Limited to the range of the bath
    "Set Low Temperature Limit": 0xC0,  # Limited to the range of the bath
    "Set High Temperature Limit": 0xE0,  # Limited to the range of the bath
    "Set Heat Proportional Band": 0xF1,  # (P = 0.1-99.9)
    "Set Heat Integral": 0xF2,  # (I = 0-9.99)
    "Set Heat Derivative": 0xF3,  # (D = 0-5.0)
    "Set Cool Proportional Band": 0xF4,  # (P = 0.1-99.9)
    "Set Cool Integral": 0xF5,  # (I = 0-9.99)
    "Set Cool Derivative": 0xF6,  # (D = 0-5.0)
    # Exclude these from the dictionary of commands as they have non-generic responses
    # Handle them one-off as necessary
    # "Read Acknowledge": 0x00,
    # "Read Status": 0x09,
    # "Set On/Off Array": 0x81,
}

SET_ON_OFF_ARRAY_COMMAND = 0x81
ERROR_RESPONSE_COMMAND = 0x0F


_QUALIFIER_HEX_TO_PRECISION = {
    0x10: 0.1,
    0x20: 0.01,
    0x11: 0.1,  # Units: degrees C
    0x21: 0.01,  # Units: degrees C
}
