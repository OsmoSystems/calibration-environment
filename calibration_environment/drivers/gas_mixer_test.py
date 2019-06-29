from unittest import mock
from unittest.mock import sentinel

import math
import pandas as pd
import pytest

import calibration_environment.drivers.gas_mixer as module


@pytest.fixture
def mock_send_serial_command_and_get_response(mocker):
    return mocker.patch.object(module, "send_serial_command_str_and_get_response")


@pytest.mark.parametrize(
    "alarm_str, expected",
    [("2199552", True), ("0", False), ("4096", False), (str(0x008000), True)],
)
def test_has_low_feed_pressure(alarm_str, expected):
    actual = module._has_low_feed_pressure(alarm_str)
    assert actual == expected


class TestPpbConversions:
    fractions_and_corresponding_ppbs = [
        (0.005, "5000000"),
        (0, "0"),
        (math.pi / 10, "314159265"),
    ]

    @pytest.mark.parametrize("fraction, ppb", fractions_and_corresponding_ppbs)
    def test_ppb_to_fraction(self, fraction, ppb):
        assert module._ppb_to_fraction("5000000") == 0.005

    @pytest.mark.parametrize("fraction, ppb", fractions_and_corresponding_ppbs)
    def test_fraction_to_ppb(self, fraction, ppb):
        assert module._fraction_to_ppb_str(fraction) == ppb

    @pytest.mark.parametrize("from_mfc, expected", [("------", 0), (str(1e8), 0.1)])
    def _parse_flow_fraction(self, from_mfc, expected):
        assert module._fraction_to_ppb_str(from_mfc) == expected


class TestSendSequenceWithExpectedResponses:
    def test_sends_appropriate_sequence_when_response_is_as_expected(
        self, mock_send_serial_command_and_get_response
    ):
        mock_send_serial_command_and_get_response.side_effect = [
            sentinel.response_one,
            sentinel.response_two,
        ]

        module._send_sequence_with_expected_responses(
            sentinel.port,
            [
                (sentinel.call_one, sentinel.response_one),
                (sentinel.call_two, sentinel.response_two),
            ],
        )

        expected_calls = [
            mock.call(sentinel.call_one, sentinel.port),
            mock.call(sentinel.call_two, sentinel.port),
        ]

        actual_calls = mock_send_serial_command_and_get_response.call_args_list
        assert actual_calls == expected_calls

    def test_raises_exception_and_stops_further_calls_when_return_value_unexpected(
        self, mock_send_serial_command_and_get_response
    ):
        mock_send_serial_command_and_get_response.side_effect = [
            sentinel.response_one,
            sentinel.surprise,  # !
        ]

        with pytest.raises(module.UnexpectedMixerResponse, match="surprise"):
            module._send_sequence_with_expected_responses(
                sentinel.port,
                [
                    (sentinel.call_one, sentinel.response_one),
                    (sentinel.call_two, sentinel.response_two),
                    (sentinel.call_three, sentinel.response_three),
                ],
            )

        expected_calls = [
            mock.call(sentinel.call_one, sentinel.port),
            mock.call(sentinel.call_two, sentinel.port),
        ]

        actual_calls = mock_send_serial_command_and_get_response.call_args_list
        assert actual_calls == expected_calls


class TestParseMixerStatus:
    @pytest.mark.parametrize(
        "name, mixer_status_str, expected",
        [
            (
                "Stopped due to N2 low",
                (
                    "A 0 30 2199568 14 7 4 2 Y - -00.00 +00.00 +0001459 ---------- "
                    "2199568 +000.0 +00.00 +921 +1000000000 04096 +018.6 -0.000 +539 +0000000000"
                ),
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
                (
                    "A 0 2 4096 14 7 4 2 Y - +00.19 +05.00 +0001463 ---------- "
                    "04096 +020.6 +02.50 +923 +0500000000 04096 +017.2 +2.500 +540 +0500000000"
                ),
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
                (
                    "A 0 6 4096 14 7 4 2 Y - -00.01 +00.00 +0001464 ---------- "
                    "04096 +022.7 +00.00 +923 +0000000000 04096 +018.5 +0.000 +541 +1000000000"
                ),
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
            (
                "Has not run yet - dashes for fractions",
                (
                    "A 0 6 4096 14 7 4 2 Y - -00.01 +00.00 +0001464 ---------- "
                    "04096 +022.7 +00.00 +923 ---------- 04096 +018.5 +0.000 +541 ----------"
                ),
                pd.Series(
                    {
                        "flow rate (SLPM)": 0,
                        "mix pressure (mmHg)": -0.01,
                        "low feed pressure alarm": False,
                        "low feed pressure alarm - N2": False,
                        "low feed pressure alarm - O2 source gas": False,
                        "N2 fraction in mix": 0,
                        "O2 source gas fraction in mix": 0,
                    }
                ),
            ),
        ],
    )
    def test_mixer_status(self, name, mixer_status_str, expected):
        actual = module._parse_mixer_status(mixer_status_str)
        pd.testing.assert_series_equal(actual, expected)

    @pytest.mark.parametrize(
        "pressure_and_flow_units_str, should_raise",
        [("14 7", False), ("14 6", True), ("10 7", True), ("99 99", True)],
    )
    def test_blows_up_if_units_incorrectly_set(
        self, pressure_and_flow_units_str, should_raise
    ):
        mixer_status_str = (
            f"A 0 6 4096 {pressure_and_flow_units_str} 4 2 Y - -00.01 +00.00 +0001464 ---------- "
            "04096 +022.7 +00.00 +923 ---------- 04096 +018.5 +0.000 +541 ----------"
        )
        if should_raise:
            with pytest.raises(module.UnexpectedMixerResponse, match="units"):
                module._parse_mixer_status(mixer_status_str)
        else:
            # This is more of a meta-test that everything is fine with this test when the units are correct
            module._parse_mixer_status(mixer_status_str)


class TestGetMixerStatus:
    def test_happy_path(self, mock_send_serial_command_and_get_response, mocker):
        mock_send_serial_command_and_get_response.return_value = (
            sentinel.serial_response
        )
        mock_parse_mixer_status = mocker.patch.object(
            module, "_parse_mixer_status", return_value=sentinel.parsed_status
        )

        status = module.get_mixer_status(sentinel.port)

        mock_send_serial_command_and_get_response.assert_called_with(
            "A QMXS", sentinel.port
        )
        mock_parse_mixer_status.assert_called_with(sentinel.serial_response)
        assert status == sentinel.parsed_status

    def test_no_response_error(self, mock_send_serial_command_and_get_response, mocker):
        mock_send_serial_command_and_get_response.return_value = ""

        with pytest.raises(module.UnexpectedMixerResponse, match="No response"):
            module.get_mixer_status(sentinel.port)


class TestParseGasIds:
    def test_parses_gas_ids(self):
        expected = pd.Series({"N2": 1, "O2 source gas": 4})

        actual = module._parse_gas_ids("A 1 4")

        pd.testing.assert_series_equal(actual, expected)


class TestStopFlow:
    def test_makes_appropriate_serial_call_and_doesnt_blow_up_in_happy_case(
        self, mock_send_serial_command_and_get_response
    ):
        mock_send_serial_command_and_get_response.return_value = (
            f"A {module.MIX_STATE_CODE_STOPPED_OK}"
        )

        module.stop_flow(mock.sentinel.port)

        mock_send_serial_command_and_get_response.assert_called_with(
            "A MXRS 2", mock.sentinel.port
        )

    def test_asserts_mixer_state(self, mock_send_serial_command_and_get_response):
        # Mixer is still mixing after we asked it to stop! This could be any other code
        mock_send_serial_command_and_get_response.return_value = (
            f"A {module.MIX_STATE_CODE_MIXING}"
        )

        with pytest.raises(module.UnexpectedMixerResponse, match="Device is mixing."):
            module.stop_flow(mock.sentinel.port)


class TestAssertMixerState:
    def test_mixer_state_matches_doesnt_error(self):
        module._assert_mixer_state("A 3", 3)

    def test_mixer_state_mismatch_provides_helpful_error(self):
        expected_code = 2  # should be mixing
        actual_code = 5  # There's an alarm
        with pytest.raises(module.UnexpectedMixerResponse, match="alarm"):
            module._assert_mixer_state(f"A {actual_code}", expected_code)


class TestAssertValidMix:
    @pytest.mark.parametrize(
        "flow_rate_slpm, o2_source_gas_fraction, should_raise",
        [(5, 0.1, False), (99, 99, True)],
    )
    def test_raises_appropriately(
        self, flow_rate_slpm, o2_source_gas_fraction, should_raise
    ):
        if should_raise:
            with pytest.raises(ValueError, match="mixer only goes up to"):
                module._assert_valid_mix(flow_rate_slpm, o2_source_gas_fraction)
        else:
            module._assert_valid_mix(flow_rate_slpm, o2_source_gas_fraction)


class TestStartConstantFlowMix:
    @pytest.mark.parametrize(
        "target_o2_fraction, o2_source_gas_o2_fraction, expected_o2_source_gas_fraction",
        [(1, 1, 1), (0.5, 1, 0.5), (0.5, 0.5, 1), (0.1, 0.2, 0.5)],
    )
    def test_get_o2_source_gas_fraction(
        self,
        target_o2_fraction,
        o2_source_gas_o2_fraction,
        expected_o2_source_gas_fraction,
    ):
        actual = module._get_o2_source_gas_fraction(
            target_o2_fraction, o2_source_gas_o2_fraction
        )
        assert actual == expected_o2_source_gas_fraction

    def test_get_o2_source_gas_fraction_errors_when_ratio_is_too_high(self):
        with pytest.raises(ValueError, match="%"):
            module._get_o2_source_gas_fraction(
                target_o2_fraction=0.5, o2_source_gas_o2_fraction=0.2
            )

    def test_calls_appropriate_sequence(self, mocker):
        # Most implementation details of this function are tested manually or verified by mypy.
        # This is just a smoke test
        mock_send_sequence = mocker.patch.object(
            module, "_send_sequence_with_expected_responses"
        )

        module.start_constant_flow_mix(
            sentinel.port,
            target_flow_rate_slpm=5,
            target_o2_fraction=0.1,
            o2_source_gas_o2_fraction=0.5,
        )
        mock_send_sequence.assert_called_with(
            sentinel.port,
            [
                ("A MXRM 3", "A 3"),
                ("A MXRFF 2.5", "A 2.50 7 SLPM"),
                ("A MXMF 800000000, 200000000", "A 800000000 200000000"),
                ("A MXRFF 5", "A 5.00 7 SLPM"),
                ("A MXRS 1", "A 2"),
            ],
        )