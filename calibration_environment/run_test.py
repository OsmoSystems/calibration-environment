import pytest
import pandas as pd

from .configure import CalibrationConfiguration
from . import run as module


@pytest.fixture
def mock_drivers(mocker):
    mocker.patch.object(module.gas_mixer, "start_constant_flow_mix")
    mocker.patch.object(module.gas_mixer, "stop_flow")
    mocker.patch.object(module.gas_mixer, "get_mixer_status")
    mocker.patch.object(module.gas_mixer, "get_gas_ids")

    mocker.patch.object(module.water_bath, "send_command_and_parse_response")
    mocker.patch.object(module.water_bath, "initialize")
    mocker.patch.object(module.water_bath, "send_settings_command_and_parse_response")


@pytest.fixture
def mock_get_all_sensor_data(mocker):
    mock_get_all_sensor_data = mocker.patch.object(module, "get_all_sensor_data")
    mock_get_all_sensor_data.return_value = pd.Series({"data": 1}).add_prefix("stub ")


def test_csv_is_created(tmp_path, mocker, mock_drivers, mock_get_all_sensor_data):
    output_filepath = tmp_path / "test.csv"

    setpoint_configuration = pd.DataFrame(
        {
            "temperature": [15, 25],
            "flow_rate_slpm": [2.5, 2.5],
            "o2_target_gas_fraction": [50, 50],
            "hold_time": [0.1, 0.1],
        }
    )

    expected_csv = pd.DataFrame(
        {
            "iteration": 0,
            "o2 source gas fraction": 0.21,
            "setpoint flow rate": 2.5,
            "setpoint hold time": 0.1,
            "setpoint target gas fraction": 50.0,
            "setpoint temperature": [15.0, 25.0],
            "stub data": 1,
        }
    )

    mocker.patch.object(
        module, "get_calibration_configuration"
    ).return_value = CalibrationConfiguration(
        setpoint_sequence_csv_filepath="experiment.csv",
        setpoints=setpoint_configuration,
        com_ports={"gas_mixer": "COM22", "water_bath": "COM21"},
        o2_source_gas_fraction=0.21,
        loop=False,
        output_csv_filepath=output_filepath,
        collection_interval=0.1,
    )

    module.run([])

    output_csv = pd.read_csv(output_filepath).drop(columns=["timestamp"])

    pd.testing.assert_frame_equal(output_csv, expected_csv)
