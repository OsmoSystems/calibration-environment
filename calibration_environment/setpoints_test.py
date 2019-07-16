import pandas as pd

from . import setpoints as module


class TestValidateSetpoints:
    def test_returns_expected_column_names(self):
        setpoints = pd.DataFrame(
            [{"temperature": 15, "flow_rate_slpm": 5, "o2_target_gas_fraction": 0.5}]
        )
        o2_source_gas_fraction = 1

        invalid_setpoints = module.validate_setpoints(setpoints, o2_source_gas_fraction)

        expected_column_names = set(
            [
                "temperature too low",
                "temperature too high",
                "target gas O2 fraction too high",
                "O2 flow rate too high",
                "O2 flow rate too low",
                "N2 flow rate too high",
                "N2 flow rate too low",
            ]
        )

        assert set(invalid_setpoints.columns) == expected_column_names

    def test_returns_invalid_setpoints(self):
        # O2 flow rate = 22 * .5 = 11
        # N2 flow rate = 22 - 11 = 11
        setpoints = pd.DataFrame(
            [{"temperature": 101, "flow_rate_slpm": 22, "o2_target_gas_fraction": 0.5}]
        )
        o2_source_gas_fraction = 1
        expected_errors = [
            "temperature too high",
            "O2 flow rate too high",
            "N2 flow rate too high",
        ]

        invalid_setpoints = module.validate_setpoints(setpoints, o2_source_gas_fraction)

        expected_error_columns = invalid_setpoints[expected_errors]

        assert len(invalid_setpoints) == 1
        assert expected_error_columns.all().all()
