import datetime
from unittest.mock import Mock, sentinel

import pandas as pd
import pytest

from .data_logging import EquilibrationStatus
from .equilibrate import (
    _TIMESTAMP_FIELD_NAME,
    _YSI_DO_MMHG_FIELD_NAME,
    _YSI_TEMPERATURE_FIELD_NAME,
)
from . import equilibrate as module


class TestIsFieldEquilibrated:
    def test_success(self):
        field_name = sentinel.field_name
        max_variation = 0.1
        min_stable_time = datetime.timedelta(minutes=5)
        now = datetime.datetime.now()
        five_minutes_ago = now - datetime.timedelta(minutes=5)
        test_data = [
            {field_name: 10.3, _TIMESTAMP_FIELD_NAME: five_minutes_ago},
            {field_name: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]

        assert module._is_field_equilibrated(
            pd.DataFrame(test_data), field_name, max_variation, min_stable_time
        )

    def test_has_enough_data_and_not_equilibrated(self):
        field_name = sentinel.field_name
        max_variation = 0.1
        min_stable_time = datetime.timedelta(minutes=5)
        now = datetime.datetime.now()
        five_minutes_ago = now - datetime.timedelta(minutes=5)
        test_data = [
            {field_name: 10.0, _TIMESTAMP_FIELD_NAME: five_minutes_ago},
            {field_name: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]

        assert not module._is_field_equilibrated(
            pd.DataFrame(test_data), field_name, max_variation, min_stable_time
        )

    def test_not_enough_data(self):
        field_name = sentinel.field_name
        max_variation = 0.1
        min_stable_time = datetime.timedelta(minutes=5)
        now = datetime.datetime.now()
        four_minutes_ago = now - datetime.timedelta(minutes=4)
        test_data = [
            {field_name: 10.3, _TIMESTAMP_FIELD_NAME: four_minutes_ago},
            {field_name: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]

        assert not module._is_field_equilibrated(
            pd.DataFrame(test_data), field_name, max_variation, min_stable_time
        )

    def test_ignores_old_data(self):
        field_name = sentinel.field_name
        max_variation = 0.1
        min_stable_time = datetime.timedelta(minutes=5)
        now = datetime.datetime.now()
        four_minutes_ago = now - datetime.timedelta(minutes=4)
        over_five_minutes_ago = now - datetime.timedelta(minutes=10)
        test_data = [
            {field_name: 4.3, _TIMESTAMP_FIELD_NAME: over_five_minutes_ago},
            {field_name: 10.3, _TIMESTAMP_FIELD_NAME: four_minutes_ago},
            {field_name: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]

        assert module._is_field_equilibrated(
            pd.DataFrame(test_data), field_name, max_variation, min_stable_time
        )


@pytest.fixture
def mock_sleep(mocker):
    return mocker.patch.object(module, "sleep")


@pytest.fixture
def mock_check_status(mocker):
    return mocker.patch.object(module, "check_status")


class TestWaitForEquilibration:
    @staticmethod
    def _mock_collect_data_to_csv(mocker, temperature_readings):
        sensor_data_sequence = [
            pd.Series({_YSI_TEMPERATURE_FIELD_NAME: t}) for t in temperature_readings
        ]
        return mocker.patch.object(
            module, "collect_data_to_csv", side_effect=sensor_data_sequence
        )

    @staticmethod
    def _mock_is_field_equilibrated(mocker, return_sequence):
        return mocker.patch.object(
            module, "_is_field_equilibrated", side_effect=return_sequence
        )

    def test_checks_equilibration_on_all_readings(
        self, mocker, mock_sleep, mock_check_status
    ):
        temperature_readings = (
            sentinel.temperature_reading_one,
            sentinel.temperature_reading_two,
        )
        is_field_equilibrated_sequence = (False, True)

        self._mock_collect_data_to_csv(mocker, temperature_readings)
        mock_is_field_equilibrated = self._mock_is_field_equilibrated(
            mocker, is_field_equilibrated_sequence
        )

        calibration_configuration = Mock(com_ports=sentinel.com_ports)

        module._wait_for_equilibration(
            calibration_configuration,
            sentinel.setpoint,
            sentinel.loop_count,
            sentinel.equilibration_status,
            sentinel.field_name,
            sentinel.max_variation,
            sentinel.min_stable_time,
        )

        assert mock_is_field_equilibrated.call_count == len(temperature_readings)

        # make sure it is checking for equilibration on the full set of readings
        # fmt: off
        last_is_field_equilibrated_call_args = mock_is_field_equilibrated.call_args_list[-1][0]
        # fmt: on
        final_sensor_data_log = last_is_field_equilibrated_call_args[0]
        row_count = final_sensor_data_log.shape[0]
        assert row_count == len(temperature_readings)

    def test_calls_collect_data_to_csv_and_check_status(
        self, mocker, mock_sleep, mock_check_status
    ):
        temperature_readings = (sentinel.temperature_reading_one,)
        is_field_equilibrated_sequence = (True,)

        mock_collect_data_to_csv = self._mock_collect_data_to_csv(
            mocker, temperature_readings
        )
        self._mock_is_field_equilibrated(mocker, is_field_equilibrated_sequence)

        calibration_configuration = Mock(com_ports=sentinel.com_ports)

        module._wait_for_equilibration(
            calibration_configuration,
            sentinel.setpoint,
            sentinel.loop_count,
            sentinel.equilibration_status,
            sentinel.field_name,
            sentinel.max_variation,
            sentinel.min_stable_time,
        )

        mock_collect_data_to_csv.assert_called_with(
            sentinel.setpoint,
            calibration_configuration,
            loop_count=sentinel.loop_count,
            equilibration_status=sentinel.equilibration_status,
        )
        mock_check_status.assert_called_with(calibration_configuration.com_ports)


class TestWaitForTemperatureEquilibration:
    def test_calls_wait_for_equilibration(self, mocker):
        sensor_data = pd.DataFrame(
            {_YSI_TEMPERATURE_FIELD_NAME: [sentinel.ysi_temperature_value]}
        )
        mock_wait_for_equilibration = mocker.patch.object(
            module, "_wait_for_equilibration", return_value=sensor_data
        )

        module.wait_for_temperature_equilibration(
            sentinel.calibration_configuration, sentinel.setpoint, sentinel.loop_count
        )

        mock_wait_for_equilibration.assert_called_with(
            sentinel.calibration_configuration,
            sentinel.setpoint,
            sentinel.loop_count,
            EquilibrationStatus.TEMPERATURE,
            _YSI_TEMPERATURE_FIELD_NAME,
            module._TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION,
            module._TEMPERATURE_MINIMUM_STABLE_TIME,
        )


class TestWaitForDoEquilibration:
    def test_calls_wait_for_equilibration(self, mocker):
        sensor_data = pd.DataFrame(
            {_YSI_DO_MMHG_FIELD_NAME: [sentinel.ysi_do_mmhg_value]}
        )
        mock_wait_for_equilibration = mocker.patch.object(
            module, "_wait_for_equilibration", return_value=sensor_data
        )

        module.wait_for_do_equilibration(
            sentinel.calibration_configuration, sentinel.setpoint, sentinel.loop_count
        )

        mock_wait_for_equilibration.assert_called_with(
            sentinel.calibration_configuration,
            sentinel.setpoint,
            sentinel.loop_count,
            EquilibrationStatus.DO,
            _YSI_DO_MMHG_FIELD_NAME,
            module._DO_MAXIMUM_EQUILIBRATED_VARIATION_MMHG,
            module._DO_MINIMUM_STABLE_TIME,
        )
