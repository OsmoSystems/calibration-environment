from unittest.mock import sentinel, call

import pytest

import calibration_environment.status as module


@pytest.fixture
def mock_status_checks(mocker):
    return (
        mocker.patch.object(module.gas_mixer, "assert_status_ok_with_retry"),
        mocker.patch.object(module.water_bath, "assert_status_ok"),
        mocker.patch.object(module.ysi, "get_sensor_reading_with_retry"),
    )


@pytest.fixture
def mock_logger(mocker):
    return mocker.patch.object(module, "logger")


MOCK_PORTS = {
    "gas_mixer": sentinel.gas_mixer_port,
    "water_bath": sentinel.water_bath_port,
    "ysi": sentinel.ysi_port,
}


class TestCheckStatus:
    def test_happy_path_does_debug_log(self, mock_logger, mock_status_checks):

        module.check_status(MOCK_PORTS)

        mock_logger.exception.assert_not_called()
        mock_logger.debug.assert_called_once_with("Clean status check")

    def test_status_error_logged_and_raised_with_contents(
        self, mock_logger, mock_status_checks
    ):
        mock_gas_mixer_status_check, mock_water_bath_status_check, mock_ysi_status_check = (
            mock_status_checks
        )

        mock_gas_mixer_status_check.side_effect = module.gas_mixer.GasMixerStatusError(
            "contents"
        )

        with pytest.raises(
            module.CalibrationSequenceAbort,
            match=r"\[GasMixerStatusError\('contents',\)]",
        ):
            module.check_status(MOCK_PORTS)

        mock_logger.exception.assert_has_calls(
            [call("Gas mixer status check failed")], any_order=True
        )
        mock_logger.debug.assert_not_called()

    def test_multiple_exceptions_logged_and_returned(
        self, mock_logger, mock_status_checks
    ):
        mock_gas_mixer_status_check, mock_water_bath_status_check, mock_ysi_status_check = (
            mock_status_checks
        )

        mock_gas_mixer_status_check.side_effect = module.gas_mixer.GasMixerStatusError
        mock_water_bath_status_check.side_effect = (
            module.water_bath.exceptions.WaterBathStatusError()
        )
        mock_ysi_status_check.side_effect = module.serial.SerialException

        with pytest.raises(
            module.CalibrationSequenceAbort,
            match=r"GasMixerStatusError.*WaterBathStatusError.*SerialException",
        ):
            module.check_status(MOCK_PORTS)

        # logger.exception should get called twice for each error: once to introduce it and once with the traceback
        assert mock_logger.exception.call_count == 3
        mock_logger.debug.assert_not_called()

    def test_unexpected_exception_still_raises(self, mock_status_checks):
        mock_gas_mixer_status_check, mock_water_bath_status_check, mock_ysi_status_check = (
            mock_status_checks
        )

        mock_gas_mixer_status_check.side_effect = RecursionError

        with pytest.raises(RecursionError):
            module.check_status(MOCK_PORTS)
