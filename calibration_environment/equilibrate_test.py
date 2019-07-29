import datetime
from unittest.mock import Mock, sentinel

import pandas as pd
import pytest

from .equilibrate import _YSI_TEMPERATURE_FIELD_NAME, _TIMESTAMP_FIELD_NAME
from . import equilibrate as module


class TestIsTemperatureEquilibrated:
    def test_success(self):
        now = datetime.datetime.now()
        five_minutes_ago = now - datetime.timedelta(minutes=5)
        test_data = [
            {
                _YSI_TEMPERATURE_FIELD_NAME: 10.3,
                _TIMESTAMP_FIELD_NAME: five_minutes_ago,
            },
            {_YSI_TEMPERATURE_FIELD_NAME: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]
        test_data = pd.DataFrame(test_data)
        assert module._is_temperature_equilibrated(test_data)

    def test_not_enough_data(self):
        now = datetime.datetime.now()
        four_minutes_ago = now - datetime.timedelta(minutes=4)
        test_data = [
            {
                _YSI_TEMPERATURE_FIELD_NAME: 10.3,
                _TIMESTAMP_FIELD_NAME: four_minutes_ago,
            },
            {_YSI_TEMPERATURE_FIELD_NAME: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]
        test_data = pd.DataFrame(test_data)
        assert not module._is_temperature_equilibrated(test_data)

    def test_ignores_old_data(self):
        now = datetime.datetime.now()
        four_minutes_ago = now - datetime.timedelta(minutes=4)
        over_five_minutes_ago = now - datetime.timedelta(minutes=10)
        test_data = [
            {
                _YSI_TEMPERATURE_FIELD_NAME: 4.3,
                _TIMESTAMP_FIELD_NAME: over_five_minutes_ago,
            },
            {
                _YSI_TEMPERATURE_FIELD_NAME: 10.3,
                _TIMESTAMP_FIELD_NAME: four_minutes_ago,
            },
            {_YSI_TEMPERATURE_FIELD_NAME: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]
        test_data = pd.DataFrame(test_data)
        assert module._is_temperature_equilibrated(test_data)


@pytest.fixture
def mock_sleep(mocker):
    return mocker.patch.object(module, "sleep")


@pytest.fixture
def mock_write_row_to_csv(mocker):
    return mocker.patch.object(module, "write_row_to_csv")


class TestWaitForTemperatureEquilibration:
    @staticmethod
    def _mock_get_all_sensor_data(mocker, temperature_readings):
        get_all_sensor_data_sequence = [
            pd.Series({_YSI_TEMPERATURE_FIELD_NAME: t}) for t in temperature_readings
        ]
        return mocker.patch.object(
            module, "get_all_sensor_data", side_effect=get_all_sensor_data_sequence
        )

    @staticmethod
    def _mock_is_temperature_equilibrated(mocker, return_sequence):
        return mocker.patch.object(
            module, "_is_temperature_equilibrated", side_effect=return_sequence
        )

    def test_checks_equilibration_on_all_readings(
        self, mocker, mock_write_row_to_csv, mock_sleep
    ):
        temperature_readings = (
            sentinel.temperature_reading_one,
            sentinel.temperature_reading_two,
        )
        is_temperature_equilibrated_sequence = (False, True)

        self._mock_get_all_sensor_data(mocker, temperature_readings)
        mock_is_temperature_equilibrated = self._mock_is_temperature_equilibrated(
            mocker, is_temperature_equilibrated_sequence
        )

        calibration_configuration = Mock(com_ports=sentinel.com_ports)

        module.wait_for_temperature_equilibration(calibration_configuration)
        assert mock_is_temperature_equilibrated.call_count == len(temperature_readings)

        # make sure it is checking for equilibration  on the full set of readings
        final_sensor_data_log = mock_is_temperature_equilibrated.call_args[0][0]
        row_count = final_sensor_data_log.shape[0]
        assert row_count == len(temperature_readings)

    def test_calls_write_row_to_csv(self, mocker, mock_write_row_to_csv, mock_sleep):
        temperature_readings = (
            sentinel.temperature_reading_one,
            sentinel.temperature_reading_two,
        )
        is_temperature_equilibrated_sequence = (False, True)

        self._mock_get_all_sensor_data(mocker, temperature_readings)
        self._mock_is_temperature_equilibrated(
            mocker, is_temperature_equilibrated_sequence
        )
        calibration_configuration = Mock(com_ports=sentinel.com_ports)

        module.wait_for_temperature_equilibration(calibration_configuration)
        assert mock_write_row_to_csv.call_count == len(temperature_readings)
