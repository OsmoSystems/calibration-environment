import math
import pandas as pd
import pytest

import calibration_environment.drivers.mfc as module


@pytest.mark.parametrize(
    "alarm_str, expected",
    [("2199552", True), ("0", False), ("4096", False), (str(0x008000), True)],
)
def test_has_low_feed_pressure(alarm_str, expected):
    actual = module._has_low_feed_pressure(alarm_str)
    assert actual == expected


class TestPpbConversions:
    def test_ppb_to_fraction(self):
        assert module._ppb_to_fraction("5000000") == 0.005

    def test_fraction_to_ppb(self):
        assert module._fraction_to_ppb(0.005) == "5000000"

    def test_fraction_to_ppb_rounding(self):
        assert module._fraction_to_ppb(math.pi / 10) == "314159265"


class TestParseMixerStatus:
    @pytest.mark.parametrize(
        "name, mixer_status_str, expected",
        [
            (
                "Stopped due to N2 low",
                "A 0 30 2199568 10 7 4 2 Y - -00.00 +00.00 +0001459 ---------- "
                "2199568 +000.0 +00.00 +921 +1000000000 04096 +018.6 -0.000 +539 +0000000000",
                pd.Series(
                    {
                        "flow rate (SLPM)": 0,
                        "mix pressure (mmHg)": 0,
                        "low feed pressure alarm": True,
                        "low feed pressure alarm - N2": True,
                        "low feed pressure alarm - O2 source gas": False,
                        "N2 fraction in mix": 1,
                        "O2 source gas fraction in mix": 0,
                    }
                ),
            ),
            (
                "Running",
                "A 0 2 4096 10 7 4 2 Y - +00.19 +05.00 +0001463 ---------- "
                "04096 +020.6 +02.50 +923 +0500000000 04096 +017.2 +2.500 +540 +0500000000",
                pd.Series(
                    {
                        "flow rate (SLPM)": 5,
                        "mix pressure (mmHg)": 0.19,
                        "low feed pressure alarm": False,
                        "low feed pressure alarm - N2": False,
                        "low feed pressure alarm - O2 source gas": False,
                        "N2 fraction in mix": 0.5,
                        "O2 source gas fraction in mix": 0.5,
                    }
                ),
            ),
            (
                "Stopped - OK",
                "A 0 6 4096 10 7 4 2 Y - -00.01 +00.00 +0001464 ---------- "
                "04096 +022.7 +00.00 +923 +0000000000 04096 +018.5 +0.000 +541 +1000000000",
                pd.Series(
                    {
                        "flow rate (SLPM)": 0,
                        "mix pressure (mmHg)": -0.01,
                        "low feed pressure alarm": False,
                        "low feed pressure alarm - N2": False,
                        "low feed pressure alarm - O2 source gas": False,
                        "N2 fraction in mix": 0,
                        "O2 source gas fraction in mix": 1,
                    }
                ),
            ),
        ],
    )
    def test_mixer_status(self, name, mixer_status_str, expected):
        actual = module._parse_mixer_status(mixer_status_str)
        print(actual)
        pd.testing.assert_series_equal(actual, expected)
