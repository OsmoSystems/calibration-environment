import pandas as pd

from . import setpoints as module


class TestValidateSetpoints:
    def test_returns_invalid_setpoints(self):
        # O2 flow rate = 22 * .5 = 11
        # N2 flow rate = 22 - 11 = 11
        setpoints = pd.DataFrame(
            [{"temperature": 101, "flow_rate_slpm": 22, "o2_target_gas_fraction": 0.5}]
        )
        o2_source_gas_fraction = 1
        expected_errors = set(
            ["temperature > 100 C", "O2 flow rate > 2.5 SLPM", "N2 flow rate > 10 SLPM"]
        )

        invalid_setpoints = module.get_validation_errors(
            setpoints, o2_source_gas_fraction
        )

        assert len(invalid_setpoints) == 1
        assert set(invalid_setpoints.loc[0]["validation_errors"]) == expected_errors
