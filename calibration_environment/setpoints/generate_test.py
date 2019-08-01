import pandas as pd
import pytest

from calibration_environment.setpoints.constants import AVERAGE_SYSTEM_PRESSURE_MMHG
from . import generate as module


class TestSortDoWithinTemperature:
    unsorted_setpoints = pd.DataFrame(
        {"temperature": 5, "o2_fraction": [1, 3, 5, 7, 6, 4, 2, 0]}
    )

    def test_sorts_ascending_when_it_should(self):
        actual = module._sort_do_within_temperature(
            self.unsorted_setpoints, temperatures_with_ascending_do={2, 5, 7}
        )
        expected = actual.sort_values("temperature", ascending=True)
        pd.testing.assert_frame_equal(actual, expected)

    def test_sorts_descending_when_it_should(self):
        actual = module._sort_do_within_temperature(
            self.unsorted_setpoints, temperatures_with_ascending_do={90000}
        )
        expected = actual.sort_values("temperature", ascending=False)
        pd.testing.assert_frame_equal(actual, expected)

    def test_sort_ascending_works_as_expected(self):
        actual = module._sort_do_within_temperature(
            self.unsorted_setpoints, temperatures_with_ascending_do={5}
        )["o2_fraction"]

        assert actual.to_list() == [0, 1, 2, 3, 4, 5, 6, 7]


class TestGetUnorderedSetpoints:
    def test_creates_setpoint_dataframe_with_appropriate_do_and_temperature_values(
        self
    ):
        expected_setpoints = pd.DataFrame(
            {
                "temperature": [0, 0, 0, 0, 0.5, 0.5, 0.5, 0.5, 1, 1, 1, 1],
                "DO (mmHg)": [10, 11, 12, 13] * 3,
            },
            dtype=float,
        )

        expected_setpoints["o2_fraction"] = (
            expected_setpoints["DO (mmHg)"] / AVERAGE_SYSTEM_PRESSURE_MMHG
        )

        actual_setpoints = module.get_unordered_setpoints(
            min_temperature=0,
            max_temperature=1,
            temperatures_setpoint_count=3,
            min_do_mmhg=10,
            max_do_mmhg=13,
            DO_setpoint_count=4,
        )

        pd.testing.assert_frame_equal(actual_setpoints, expected_setpoints)


class TestOrderSetpoints:
    @pytest.mark.parametrize(
        "start_high_do, start_high_temp, expected_temperatures, expected_o2_fractions",
        [
            (False, True, [1, 1, 0, 0], [0.2, 0.4, 0.3, 0.1]),
            (True, False, [0, 0, 1, 1], [0.3, 0.1, 0.2, 0.4]),
            (True, True, [1, 1, 0, 0], [0.4, 0.2, 0.1, 0.3]),
            (False, False, [0, 0, 1, 1], [0.1, 0.3, 0.4, 0.2]),
        ],
    )
    def test_orders_temperature_and_do(
        self,
        start_high_do,
        start_high_temp,
        expected_temperatures,
        expected_o2_fractions,
    ):
        input_setpoints = pd.DataFrame(
            {"temperature": [0, 1, 0, 1], "o2_fraction": [0.1, 0.2, 0.3, 0.4]},
            dtype=float,
        )

        expected_setpoints = pd.DataFrame(
            {
                "temperature": expected_temperatures,
                "o2_fraction": expected_o2_fractions,
            },
            dtype=float,
        )

        actual_setpoints = module.order_setpoints(
            input_setpoints,
            start_high_do=start_high_do,
            start_high_temp=start_high_temp,
        )

        pd.testing.assert_frame_equal(actual_setpoints, expected_setpoints)


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
            "DO (mmHg)",
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
            start_high_temp=True,
            start_high_do=False,
        )

        assert isinstance(actual, pd.DataFrame)
        assert set(actual.columns) == expected_columns
        assert len(actual) == expected_n_setpoints
