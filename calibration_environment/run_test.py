import pandas as pd

from .prepare import CalibrationConfiguration
from . import run as module

# Don't sleep when running tests
module.DATA_COLLECTION_INTERVAL_SECONDS = 0


def test_csv_is_created(tmp_path, mocker):
    output_filepath = tmp_path / "test.csv"

    setpoint_configuration = pd.DataFrame(
        {
            "temperature": [15, 25],
            "flow_rate_slpm": [2.5, 2.5],
            "o2_target_gas_fraction": [50, 50],
        }
    )

    # There are a minimum of 2 data points collected at each setpoint
    # one in each of WAIT_FOR_GAS_MIXER_EQ, WAIT_FOR_SETPOINT_TIMEOUT
    expected_csv = pd.DataFrame(
        {
            "iteration": 0,
            "setpoint temperature": [15, 15, 25, 25],
            "setpoint flow rate": 2.5,
            "setpoint target gas fraction": 50,
            "o2 source gas fraction": 0.21,
            "equilibration state": [
                "WAIT_FOR_GAS_MIXER_EQ",
                "WAIT_FOR_SETPOINT_TIMEOUT",
                "WAIT_FOR_GAS_MIXER_EQ",
                "WAIT_FOR_SETPOINT_TIMEOUT",
            ],
            "temperature equilibrated": True,
            "gas mixer equilibrated": True,
            "stub data": 1,
        }
    )

    mocker.patch.object(
        module, "get_calibration_configuration"
    ).return_value = CalibrationConfiguration(
        sequence_csv="experiment.csv",
        setpoints=setpoint_configuration,
        com_port_args={"gas_mixer": "COM22", "water_bath": "COM21"},
        o2_source_gas_fraction=0.21,
        loop=False,
        dry_run=True,
        output_csv=output_filepath,
        collection_wait_time=0,  # Don't require any waiting during tests
    )

    module.run([])

    output_csv = pd.read_csv(output_filepath).drop(columns=["timestamp"])

    pd.testing.assert_frame_equal(output_csv, expected_csv, check_dtype=False)
