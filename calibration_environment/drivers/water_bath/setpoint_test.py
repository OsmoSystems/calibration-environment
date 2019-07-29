import pytest

from calibration_environment.drivers.water_bath import setpoint as module


class TestGetTemperatureValidationErrors:
    @pytest.mark.parametrize(
        "temperature, expected_errors",
        [
            (30, []),
            (module._LOW_TEMPERATURE_LIMIT - 1, ["temperature < 0 C"]),
            (module._HIGH_TEMPERATURE_LIMIT + 1, ["temperature > 100 C"]),
        ],
    )
    def test_returns_expected_validation_errors(self, temperature, expected_errors):
        validation_errors = module.get_temperature_setpoint_validation_errors(
            temperature
        )

        assert validation_errors == expected_errors
