[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

# calibration-environment

Automation and data collection tools for the Osmo calibration environment

# Usage

## Water bath

### Physical set-up
The water bath must be switched into serial communications mode by pushing the "Serial" button on the local controller.

Once the bath is in serial communications mode, it can no longer be controlled at all locally.

Note from the [datasheet](https://drive.google.com/open?id=1Tg-e1C8Ht8BE7AYzKVSqjw9bhWWxqKlz) on how to override this: 
If the unit is shut down in the serial communication mode and you need to start the unit using the local controller, simultaneously depress and hold both arrow keys for approximately 10 seconds. The display will then show the internal probe temperature, and the alarm will sound. Press the Computer LED ["Serial" button] to turn off the LED and disable serial communications. Turn the controller off using ["I/O" button]. You can now start and operate the unit with the keypad.

### API
There are three public entry points for interfacing with the water bath:

`initialize()` - Must be run first, to ensure the water bath is using the correct settings
`send_command_and_parse_response()` - Used to read and set temperature and temperature PID controls
`send_settings_command_and_parse_response()` - Used to read and set meta water bath settings (e.g. turning it on/off, precision, etc)

Check docstrings for more details on usage of each function.

Example usage:
```python
import water_bath

water_bath.initialize(port="COM21")
water_bath.send_command_and_parse_response(
    port="COM21",
    command_name="Read Internal Temperature"
)

water_bath.send_command_and_parse_response(
    port="COM21",
    command_name="Read External Sensor"
)

# Set the setpoint temperature to 27.85 C
water_bath.send_command_and_parse_response(
    port="COM21",
    command_name="Set Setpoint",
    data=27.85
)
```

Advanced usage (barebones functionality for adjusting settings):
```python
import water_bath

TURN_OFF_UNIT = water_bath.OnOffArraySettings(0,2,2,2,2,2,2,2)
TURN_OFF_SERIAL = water_bath.OnOffArraySettings(2,2,2,2,2,2,2,0)

water_bath.send_settings_command_and_parse_response(
    port="COM21",
    settings=TURN_OFF_UNIT,
)

water_bath.send_settings_command_and_parse_response(
    port="COM21",
    settings=TURN_OFF_SERIAL,
)
```


