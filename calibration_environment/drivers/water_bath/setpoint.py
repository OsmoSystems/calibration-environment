# Verification of setpoint validity for the NESLAB RTE 17 temperature-controlled water bath
from typing import List

# The water bath can operate at -24C to 150C
# so use the range at which water is liquid.
_LOW_TEMPERATURE_LIMIT = 0
_HIGH_TEMPERATURE_LIMIT = 100


def get_temperature_validation_errors(setpoint_temperature: float) -> List:
    """ Validate that a given temperature is attainable by the water bath.
        Args:
            setpoint_temperature: The desired setpoint temperature in C
        Returns:
            Pandas series with boolean flags indicating errors with this temperature.
    """
    validation_errors = {
        f"temperature < {_LOW_TEMPERATURE_LIMIT} C": setpoint_temperature
        < _LOW_TEMPERATURE_LIMIT,
        f"temperature > {_HIGH_TEMPERATURE_LIMIT} C": setpoint_temperature
        > _HIGH_TEMPERATURE_LIMIT,
    }

    return [error for error, has_error in validation_errors.items() if has_error]
