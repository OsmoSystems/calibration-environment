from unittest.mock import sentinel

import pytest

from calibration_environment.drivers.water_bath import status as module
from calibration_environment.drivers.water_bath.exceptions import WaterBathStatusError
from calibration_environment.drivers.water_bath.serial import SerialPacket


@pytest.fixture
def mock_send_command(mocker):
    return mocker.patch.object(module, "send_command")


def _construct_water_bath_status(**kwarg_overrides):
    kwargs_with_overrides = {
        **{key: False for key in module.WaterBathStatus._fields},
        **kwarg_overrides,
    }
    return module.WaterBathStatus(**kwargs_with_overrides)


class TestGetWaterBathStatus:
    def test_get_water_bath_status(self, mock_send_command):
        mock_send_command.return_value = SerialPacket.from_bytes(
            # Actual byte string observed while water bath running
            b"\xca\x00\x01\x09\x05\x00\x00\x00\x0e\x08\xda"
        )

        actual = module.get_water_bath_status(sentinel.port)
        expected = _construct_water_bath_status(
            cool_led_on=True, compressor_on=True, pump_on=True, unit_on=True
        )

        # Use _asdict for more helpful errors
        assert actual._asdict() == expected._asdict()


class TestValidateStatus:
    def test_raises_errors_when_faults_present(self):
        with pytest.raises(
            WaterBathStatusError,
            match="['rtd2_open_warn', 'rtd2_shorted', 'low_level_fault']",
        ):
            module._validate_status(
                _construct_water_bath_status(
                    rtd2_open_warn=True, low_level_fault=True, rtd2_shorted=True
                )
            )

    def test_does_not_raise_for_normal_stuff(self):
        module._validate_status(
            _construct_water_bath_status(
                cool_led_on=True, compressor_on=True, pump_on=True, unit_on=True
            )
        )


class TestIsErrorKey:
    def test_chooses_correct_keys(self):
        expected_error_keys = [
            "rtd1_open_fault",
            "rtd1_shorted_fault",
            "rtd1_shorted",
            "rtd3_open_fault",
            "rtd3_shorted_fault",
            "rtd3_shorted",
            "rtd2_open_fault",
            "rtd2_shorted_fault",
            "rtd2_open_warn",
            "rtd2_shorted_warn",
            "rtd2_shorted",
            "refrig_high_temp",
            "htc_fault",
            "high_fixed_temp_fault",
            "low_fixed_temp_fault",
            "high_temp_fault",
            "low_temp_fault",
            "low_level_fault",
            "high_temp_warn",
            "low_temp_warn",
            "low_level_warn",
            "unit_faulted",
        ]

        actual_error_keys = [
            status_key
            for status_key in module.WaterBathStatus._fields
            if module._is_error_key(status_key)
        ]
        assert actual_error_keys == expected_error_keys


class TestAssertWaterBathStatusOk:
    def test_gets_status_and_then_validates_it(self, mocker, mock_send_command):
        mock_validate_status = mocker.patch.object(module, "_validate_status")

        mock_send_command.return_value = SerialPacket.from_bytes(
            # Actual byte string observed while water bath running
            b"\xca\x00\x01\x09\x05\x00\x00\x00\x0e\x08\xda"
        )

        status = _construct_water_bath_status(
            cool_led_on=True, compressor_on=True, pump_on=True, unit_on=True
        )

        module.assert_water_bath_status_ok(sentinel.port)

        mock_validate_status.assert_called_with(status)
