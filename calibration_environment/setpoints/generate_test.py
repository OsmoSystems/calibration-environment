import pandas as pd
import pytest

from . import generate as module


class TestGenerateOrderedSetpoints:
    @pytest.mark.parametrize(
        "start_high_do, start_high_temperature",
        [(False, True), (True, False), (True, True), (False, False)],
    )
    def test_generates_setpoints_with_ordered_temperature_and_do(
        self, start_high_do, start_high_temperature
    ):
        expected_do_mmhg_high_first = [0.4, 0.2, 0.2, 0.4, 0.4, 0.2]
        expected_temperature_high_first = [1, 1, 0.5, 0.5, 0, 0]

        expected_setpoints = pd.DataFrame(
            {
                "temperature": expected_temperature_high_first
                if start_high_temperature
                else reversed(expected_temperature_high_first),
                "DO (approx mmHg)": expected_do_mmhg_high_first
                if start_high_do
                else reversed(expected_do_mmhg_high_first),
            },
            dtype=float,
        )

        actual_setpoints = module.generate_ordered_setpoints(
            min_temperature=0,
            max_temperature=1,
            temperatures_setpoint_count=3,
            min_do_mmhg=0.2,
            max_do_mmhg=0.4,
            do_setpoint_count=2,
            start_high_do=start_high_do,
            start_high_temperature=start_high_temperature,
        )

        pd.testing.assert_frame_equal(
            actual_setpoints[["temperature", "DO (approx mmHg)"]], expected_setpoints
        )


class TestRemoveInvalidPoints:
    def test_removes_invalid_points(self):
        sweep = pd.DataFrame(
            {"o2_fraction": [0.1, 0.2, 100], "flow_rate_slpm": 2, "temperature": 20}
        )
        actual_filtered_sweep = module.remove_invalid_points(
            sweep, o2_source_gas_o2_fraction=1
        )
        expected_sweep = sweep[:2]
        pd.testing.assert_frame_equal(actual_filtered_sweep, expected_sweep)


class TestCreateSweep:
    def test_generates_a_sweep_with_the_right_shape(self, mocker):
        # Mock out get_validation_errors so that this test isn't coupled to validation details
        mocker.patch.object(module, "get_validation_errors")

        n_temperatures = 3
        n_dos = 10
        expected_n_setpoints = n_temperatures * n_dos

        expected_columns = {
            "temperature",
            "flow_rate_slpm",
            "o2_fraction",
            "DO (approx mmHg)",
            "hold_time",
        }

        actual = module.create_sweep(
            min_temperature=10,
            max_temperature=20,
            temperatures_setpoint_count=n_temperatures,
            min_do_mmhg=10,
            max_do_mmhg=100,
            do_setpoint_count=n_dos,
            o2_source_gas_o2_fraction=0.5,
            hold_time_seconds=10,
            start_high_temperature=True,
            start_high_do=False,
        )

        assert isinstance(actual, pd.DataFrame)
        assert set(actual.columns) == expected_columns
        assert len(actual) == expected_n_setpoints
