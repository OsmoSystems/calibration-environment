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
    return mocker.patch.object(module, "get_all_sensor_data", return_value=pd.Series())


@pytest.fixture
def mock_get_calibration_configuration(mocker):
    return mocker.patch.object(module, "get_calibration_configuration")


@pytest.fixture
def mock_output_filepath(tmp_path):
    return tmp_path / "test.csv"


class TestGetAllSensorData:
    def test_adds_data_prefix_and_suffix(self, mocker):
        mocker.patch.object(
            module.gas_mixer,
            "get_mixer_status_with_retry",
            return_value=pd.Series({"status": 0, "error": False}),
        )
        mocker.patch.object(
            module.gas_mixer,
            "get_gas_ids_with_retry",
            return_value=pd.Series({"N2": 0, "O2": 1}),
        )
        mock_send_command_and_parse_response = mocker.patch.object(
            module.water_bath, "send_command_and_parse_response"
        )

        mocker.patch.object(
            module.ysi,
            "get_standard_sensor_values",
            return_value=pd.Series({"DO or something": 0, "temperature (C)": 1}),
        )

        # Return values for "Read Internal Temperature" and
        # "Read External Sensor", respectively
        mock_send_command_and_parse_response.side_effect = [15, 16]

        expected_sensor_data = pd.Series(
            {
                "gas mixer status": 0,
                "gas mixer error": False,
                "N2 gas ID": 0,
                "O2 gas ID": 1,
                "water bath internal temperature (C)": 15,
                "water bath external sensor temperature (C)": 16,
                "YSI DO or something": 0,
                "YSI temperature (C)": 1,
            }
        )

        output_sensor_data = module.get_all_sensor_data(
            {"gas_mixer": "port 1", "water_bath": "port 2", "ysi": "port 3"}
        )

        pd.testing.assert_series_equal(expected_sensor_data, output_sensor_data)


class TestCollectDataToCsv:
    default_setpoint = pd.Series(
        {"temperature": 15, "hold_time": 300, "flow_rate_slpm": 2.5, "o2_fraction": 0.2}
    )
    default_configuration = CalibrationConfiguration(
        setpoint_sequence_csv_filepath="experiment.csv",
        setpoints=default_setpoint,
        com_ports={"gas_mixer": "COM22", "water_bath": "COM21"},
        o2_source_gas_fraction=0.21,
        loop=False,
        output_csv_filepath="test.csv",
        collection_interval=0.1,
    )

    def test_saves_csv_headers(self, mock_output_filepath, mock_get_all_sensor_data):
        test_configuration = self.default_configuration._replace(
            output_csv_filepath=mock_output_filepath
        )

        module.collect_data_to_csv(
            self.default_setpoint,
            test_configuration,
            loop_count=0,
            write_headers_to_file=True,
        )

        # Use chunksize=1 to get a file reader that iterates over rows
        output_csv = pd.read_csv(mock_output_filepath, chunksize=1)
        first_row = output_csv.__next__()

        assert list(first_row) == [
            "loop count",
            "o2 source gas fraction",
            "setpoint flow rate (SLPM)",
            "setpoint hold time seconds",
            "setpoint O2 fraction",
            "setpoint temperature (C)",
            "timestamp",
        ]

    def test_skips_saving_headers(self, mock_output_filepath, mock_get_all_sensor_data):
        test_configuration = self.default_configuration._replace(
            output_csv_filepath=mock_output_filepath
        )

        module.collect_data_to_csv(
            self.default_setpoint,
            test_configuration,
            loop_count=0,
            write_headers_to_file=False,
        )

        # Use chunksize=1 to get a file reader that iterates over rows
        output_csv = pd.read_csv(mock_output_filepath, chunksize=1)
        first_row = output_csv.__next__()

        assert list(first_row) != [
            "loop count",
            "o2 source gas fraction",
            "setpoint flow rate (SLPM)",
            "setpoint hold time seconds",
            "setpoint O2 fraction",
            "setpoint temperature (C)",
            "timestamp",
        ]

    def test_saves_expected_data(self, mock_output_filepath, mock_get_all_sensor_data):
        test_setpoint = pd.Series(
            {
                "temperature": 15,
                "hold_time": 300,
                "flow_rate_slpm": 2.5,
                "o2_fraction": 0.2,
            }
        )
        test_configuration = self.default_configuration._replace(
            output_csv_filepath=mock_output_filepath, o2_source_gas_fraction=0.23
        )

        mock_get_all_sensor_data.return_value = pd.Series(
            {"value 0": 0, "value 1": 1, "value 2": 2}
        )

        module.collect_data_to_csv(
            test_setpoint, test_configuration, loop_count=0, write_headers_to_file=True
        )

        expected_csv = pd.DataFrame(
            [
                {
                    "loop count": 0,
                    "o2 source gas fraction": 0.23,
                    "setpoint flow rate (SLPM)": 2.5,
                    "setpoint hold time seconds": 300.0,
                    "setpoint O2 fraction": 0.2,
                    "setpoint temperature (C)": 15.0,
                    "value 0": 0,
                    "value 1": 1,
                    "value 2": 2,
                }
            ]
        )

        output_csv = pd.read_csv(mock_output_filepath).drop(columns=["timestamp"])

        pd.testing.assert_frame_equal(expected_csv, output_csv)


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
    ):

        expected_csv = pd.DataFrame(
            [
                {
                    "loop count": 0,
                    "o2 source gas fraction": 0.21,
                    "setpoint flow rate (SLPM)": 2.5,
                    "setpoint hold time seconds": 0.1,
                    "setpoint O2 fraction": 50.0,
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
