import pandas as pd

from .prepare import CalibrationConfiguration
from . import run as module


def test_csv_is_created(tmp_path, mocker):
    output_filepath = tmp_path / "test.csv"

    setpoint_configuration = pd.DataFrame(
        {
            "temperature": [15, 25],
            "flow_rate_slpm": [2.5, 2.5],
            "o2_target_gas_fraction": [50, 50],
        }
    )

    expected_csv = pd.DataFrame(
        {
            "setpoint_temperature": [15, 25],
            "setpoint_flow_rate": [2.5, 2.5],
            "setpoint_target_gas_fraction": [50, 50],
            "o2_source_gas_fraction": [21, 21],
            "stub_data": [1, 1],
        }
    )

    mocker.patch.object(
        module, "get_calibration_configuration"
    ).return_value = CalibrationConfiguration(
        sequence_csv="experiment.csv",
        setpoints=setpoint_configuration,
        com_port_args={"gas_mixer": "COM19", "water_bath": "COM20"},
        o2_source_gas_fraction=21,
        loop=False,
        dry_run=True,
        output_csv=output_filepath,
        read_count=1,
        collection_wait_time=0.1,
    )

    module.run([])

    output_csv = pd.read_csv(output_filepath).drop(columns=["timestamp"])

    pd.testing.assert_frame_equal(output_csv, expected_csv, check_dtype=False)
