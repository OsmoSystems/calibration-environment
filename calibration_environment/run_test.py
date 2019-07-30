from unittest.mock import sentinel

import pytest
import pandas as pd

from .configure import CalibrationConfiguration
from . import run as module


@pytest.fixture
def mock_drivers(mocker):
    mocker.patch.object(module.gas_mixer, "start_constant_flow_mix_with_retry")
    mocker.patch.object(module.gas_mixer, "stop_flow_with_retry")
    mocker.patch.object(module.gas_mixer, "get_mixer_status_with_retry")
    mocker.patch.object(module.gas_mixer, "get_gas_ids_with_retry")

    mocker.patch.object(module.water_bath, "send_command_and_parse_response")
    mocker.patch.object(module.water_bath, "initialize")
    mocker.patch.object(module.water_bath, "send_settings_command_and_parse_response")


@pytest.fixture
def mock_get_all_sensor_data(mocker):
    return mocker.patch(
        "calibration_environment.data_logging.get_all_sensor_data",
        return_value=pd.Series(),
    )


@pytest.fixture
def mock_get_calibration_configuration(mocker):
    return mocker.patch.object(module, "get_calibration_configuration")


@pytest.fixture
def mock_wait_for_equilibration(mocker):
    mocker.patch.object(module, "wait_for_do_equilibration")
    mocker.patch.object(module, "wait_for_temperature_equilibration")


@pytest.fixture
def mock_output_filepath(tmp_path):
    return tmp_path / "test.csv"


@pytest.fixture
def mock_shut_down(mocker):
    return mocker.patch.object(module, "_shut_down")


class TestRunCalibration:
    default_setpoints = pd.DataFrame(
        [
            {
                "temperature": 15,
                "flow_rate_slpm": 2.5,
                "o2_fraction": 50,
                "hold_time": 0.1,
            }
        ]
    )
    default_configuration = CalibrationConfiguration(
        setpoint_sequence_csv_filepath="experiment.csv",
        setpoints=default_setpoints,
        com_ports={"gas_mixer": "COM22", "water_bath": "COM21"},
        o2_source_gas_fraction=0.21,
        loop=False,
        output_csv_filepath="test.csv",
        collection_interval=0.1,
    )

    def test_collects_data_at_configured_rate(
        self,
        mock_output_filepath,
        mock_drivers,
        mock_get_all_sensor_data,
        mock_get_calibration_configuration,
        mock_wait_for_equilibration,
    ):
        """
        Test is configured to hold at setpoint for 0.2 seconds, and read data
        every 0.09 seconds. 0.09 is used instead of 0.1 to allow some wiggle room.
        """
        setpoint_hold_time = 0.2
        data_collection_interval = 0.09

        setpoints = pd.DataFrame(
            [
                {
                    "temperature": 15,
                    "flow_rate_slpm": 2.5,
                    "o2_fraction": 50,
                    "hold_time": setpoint_hold_time,
                }
            ]
        )

        test_configuration = self.default_configuration._replace(
            setpoints=setpoints,
            output_csv_filepath=mock_output_filepath,
            collection_interval=data_collection_interval,
        )
        mock_get_calibration_configuration.return_value = test_configuration

        module.run([])

        output_csv = pd.read_csv(mock_output_filepath)

        expected_output_rows = setpoint_hold_time // data_collection_interval
        assert len(output_csv) == expected_output_rows

    def test_correct_values_saved_to_csv(
        self,
        mock_output_filepath,
        mocker,
        mock_drivers,
        mock_get_all_sensor_data,
        mock_get_calibration_configuration,
        mock_wait_for_equilibration,
    ):

        expected_csv = pd.DataFrame(
            [
                {
                    "equilibration status": "equilibrated",
                    "loop count": 0,
                    "o2 source gas fraction": 0.21,
                    "setpoint O2 fraction": 50.0,
                    "setpoint flow rate (SLPM)": 2.5,
                    "setpoint hold time seconds": 0.1,
                    "setpoint temperature (C)": 15.0,
                    "stub data": 1,
                }
            ]
        )

        test_configuration = self.default_configuration._replace(
            output_csv_filepath=mock_output_filepath
        )
        mock_get_calibration_configuration.return_value = test_configuration
        mock_get_all_sensor_data.return_value = pd.Series({"data": 1}).add_prefix(
            "stub "
        )

        module.run([])

        output_csv = pd.read_csv(mock_output_filepath).drop(columns=["timestamp"])

        pd.testing.assert_frame_equal(expected_csv, output_csv)

    def test_shuts_down_at_end(
        self,
        mock_output_filepath,
        mocker,
        mock_drivers,
        mock_get_all_sensor_data,
        mock_get_calibration_configuration,
        mock_shut_down,
        mock_wait_for_equilibration,
    ):
        mock_get_calibration_configuration.return_value = self.default_configuration._replace(
            output_csv_filepath=mock_output_filepath
        )

        module.run([])

        mock_shut_down.assert_called()

    @pytest.mark.parametrize(
        "function_that_might_raise",
        [
            (module.gas_mixer, "start_constant_flow_mix_with_retry"),
            (module.water_bath, "send_command_and_parse_response"),
            (module.water_bath, "initialize"),
            (module, "collect_data_to_csv"),
        ],
    )
    def test_shuts_down_after_error(
        self,
        mock_output_filepath,
        mocker,
        mock_drivers,
        mock_get_all_sensor_data,
        mock_get_calibration_configuration,
        mock_shut_down,
        mock_wait_for_equilibration,
        function_that_might_raise,
    ):
        mock_get_calibration_configuration.return_value = self.default_configuration._replace(
            output_csv_filepath=mock_output_filepath
        )

        mocker.patch.object(*function_that_might_raise).side_effect = Exception()

        # The expectation is that the Exception is raised and bubbled up, but the code
        # in the finally block still gets called, so the system still gets shut down
        with pytest.raises(Exception):
            module.run([])

        mock_shut_down.assert_called()


class TestShutDown:
    def test_shuts_down_gas_mixer_and_water_bath(
        self, mocker, mock_wait_for_equilibration
    ):
        mock_gas_mixer_shutdown = mocker.patch.object(
            module.gas_mixer, "stop_flow_with_retry"
        )
        mock_water_bath_shutdown = mocker.patch.object(
            module.water_bath, "send_settings_command_and_parse_response"
        )

        module._shut_down(sentinel.gas_mixer_com_port, sentinel.water_bath_com_port)

        mock_gas_mixer_shutdown.assert_called()
        mock_water_bath_shutdown.assert_called()

    def test_shuts_down_water_bath_if_gas_mixer_raises(
        self, mocker, mock_wait_for_equilibration
    ):
        mock_gas_mixer_shutdown = mocker.patch.object(
            module.gas_mixer, "stop_flow_with_retry", side_effect=Exception()
        )
        mock_water_bath_shutdown = mocker.patch.object(
            module.water_bath, "send_settings_command_and_parse_response"
        )

        # The expectation is that the Exception is raised and bubbled up, but the code
        # in the finally block still gets called, so the water bath still gets shut down
        with pytest.raises(Exception):
            module._shut_down(sentinel.gas_mixer_com_port, sentinel.water_bath_com_port)

        mock_gas_mixer_shutdown.assert_called()
        mock_water_bath_shutdown.assert_called()
