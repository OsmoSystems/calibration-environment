from unittest import mock
from unittest.mock import sentinel

import math
import pandas as pd
import pytest

import calibration_environment.drivers.gas_mixer as module


@pytest.fixture
def mock_send_serial_command_and_get_response(mocker):
    return mocker.patch.object(module, "send_serial_command_str_and_parse_response")


class TestMixControllerStateCode:
    EXPECTED_EMO_STRING = (
        'MixControllerState #0: "Emergency Motion Off (EMO) is active."'
    )
    EMO_CODE = module._MixControllerStateCode(0)

    def test_str_representation(self):
        assert str(self.EMO_CODE) == self.EXPECTED_EMO_STRING


class TestSendSerialCommandStrAndGetResponse:
    def test_calls_with_appropriate_line_ending_and_conversion(self, mocker):
        mock_serial_sender = mocker.patch.object(
            module, "send_serial_command_and_get_response"
        )

        command_str = "test command"
        expected_command_bytes = b"test command\r"
        module.send_serial_command_str_and_parse_response(command_str, sentinel.port)

        mock_serial_sender.assert_called_with(
            port=sentinel.port,
            command=expected_command_bytes,
            baud_rate=module._ALICAT_BAUD_RATE,
            response_terminator=module._ALICAT_SERIAL_TERMINATOR_BYTE,
            timeout=1,
        )

    def test_strips_terminator_from_response(self, mocker):
        response_bytes = b"response\r"
        expected_cleaned_response = "response"
        mocker.patch.object(
            module, "send_serial_command_and_get_response", return_value=response_bytes
        )

        actual_cleaned_response = module.send_serial_command_str_and_parse_response(
            "command", sentinel.port
        )
        assert actual_cleaned_response == expected_cleaned_response

    def test_raises_exception_if_response_terminator_not_found(self, mocker):
        response_bytes = b"incomplete because I died while writi"
        mocker.patch.object(
            module, "send_serial_command_and_get_response", return_value=response_bytes
        )

        with pytest.raises(
            module.UnexpectedMixerResponse,
            match='did not end with alicat serial terminator "\r".',
        ):
            module.send_serial_command_str_and_parse_response("command", sentinel.port)


@pytest.mark.parametrize(
    "alarm_str, expected",
    [("2199552", True), ("0", False), ("4096", False), (str(0x008000), True)],
)
def test_has_low_feed_pressure(alarm_str, expected):
    actual = module._has_low_feed_pressure(alarm_str)
    assert actual == expected


class TestPpbConversions:
    fractions_and_corresponding_ppbs = [
        (0.005, 5000000),
        (0, 0),
        (0.8, 8e8),
        (math.pi / 10, 314159265),
    ]

    @pytest.mark.parametrize("fraction, ppb", fractions_and_corresponding_ppbs)
    def test_ppb_to_fraction(self, fraction, ppb):
        assert module._ppb_to_fraction(5000000) == 0.005

    @pytest.mark.parametrize("fraction, ppb", fractions_and_corresponding_ppbs)
    def test_fraction_to_ppb(self, fraction, ppb):
        assert module._fraction_to_ppb(fraction) == ppb

    @pytest.mark.parametrize(
        "from_mfc, expected", [("------", 0), (str(100000000), 0.1)]
    )
    def test_parse_flow_fraction(self, from_mfc, expected):
        assert module._parse_flow_fraction(from_mfc) == expected

    def test_complimentary_ppb_value(self):
        ppb_value = 999999999
        expected = 1
        assert module._complimentary_ppb_value(ppb_value) == expected


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

    def test_blows_up_if_mix_controller_sends_too_few_fields(self):
        # The MFC does this occasionally.
        # It looks as if the mix controller momentarily only reports on one of the MFCs
        # https://app.asana.com/0/819671808102776/1131541155305248/f
        mixer_status_str = (
            f"A 0 6 4096 10 7 4 2 Y - -00.01 +00.00 +0001464 ---------- "
            "04096 +022.7 +00.00 +923 ---------- 04096 +018.5"
        )

        with pytest.raises(
            module.UnexpectedMixerResponse,
            match="contained 21 fields instead of the expected 24",
        ):
            module._parse_mixer_status(mixer_status_str)


class TestGetMixerStatus:
    def test_happy_path(self, mock_send_serial_command_and_get_response, mocker):
        mock_send_serial_command_and_get_response.return_value = (
            sentinel.serial_response
        )
        mock_parse_mixer_status = mocker.patch.object(
            module, "_parse_mixer_status", return_value=sentinel.parsed_status
        )

        status = module.get_mixer_status_with_retry(sentinel.port)

        mock_send_serial_command_and_get_response.assert_called_with(
            "A QMXS", sentinel.port
        )
        mock_parse_mixer_status.assert_called_with(sentinel.serial_response)
        assert status == sentinel.parsed_status

    def test_no_response_error(self, mock_send_serial_command_and_get_response):
        mock_send_serial_command_and_get_response.return_value = ""

        with pytest.raises(module.UnexpectedMixerResponse, match="No response"):
            module._get_mixer_status(sentinel.port)


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
            f"A {module._MixControllerStateCode.stopped_ok.value}"
        )

        module.stop_flow_with_retry(mock.sentinel.port)

        mock_send_serial_command_and_get_response.assert_called_with(
            "A MXRS 2", mock.sentinel.port
        )

    def test_asserts_mixer_state(self, mock_send_serial_command_and_get_response):
        # Mixer is still mixing after we asked it to stop! This could be any other code
        mock_send_serial_command_and_get_response.return_value = (
            f"A {module._MixControllerStateCode.mixing.value}"
        )

        with pytest.raises(module.UnexpectedMixerResponse, match="Device is mixing."):
            module._stop_flow(mock.sentinel.port)


class TestAssertMixerState:
    def test_mixer_state_matches_doesnt_error(self):
        module._assert_mixer_state("A 3", [module._MixControllerStateCode(3)])

    def test_mixer_state_mismatch_provides_helpful_error(self):
        expected_code = [module._MixControllerStateCode(3)]  # should be mixing
        actual_code_number = 5  # There's an alarm
        with pytest.raises(module.UnexpectedMixerResponse, match="alarm"):
            module._assert_mixer_state(f"A {actual_code_number}", expected_code)


class TestAssertValidMix:
    @pytest.mark.parametrize(
        "setpoint_total_flow_rate, setpoint_o2_fraction, o2_source_gas_o2_fraction, expected_o2_source_gas_flow_rate",
        [
            (1, 1, 1, 1),
            (0.5, 1, 1, 0.5),
            (1, 0.5, 1, 0.5),
            (1, 0.25, 0.25, 1),
            (1, 1, 0.5, 2),
        ],
    )
    def test_get_o2_source_gas_flow_rate(
        self,
        setpoint_total_flow_rate,
        setpoint_o2_fraction,
        o2_source_gas_o2_fraction,
        expected_o2_source_gas_flow_rate,
    ):
        actual = module._get_o2_source_gas_flow_rate(
            setpoint_total_flow_rate, setpoint_o2_fraction, o2_source_gas_o2_fraction
        )
        assert actual == expected_o2_source_gas_flow_rate

    @pytest.mark.parametrize(
        "name, setpoint_total_flow_rate, setpoint_o2_fraction, expected_errors",
        [
            # Flow rates with O2 source gas fraction of 1:
            #   O2 = setpoint_total_flow_rate * setpoint_o2_fraction
            #   N2 = setpoint_total_flow_rate - O2 flow rate
            ("O2 2.5, N2 0", 2.5, 1, []),
            ("O2 0, N2 2.5", 2.5, 0, []),
            ("O2 1.25, N2 1.25", 2.5, 0.5, []),
            (
                "O2 2, N2 -1",
                1,
                2,
                [
                    "setpoint gas O2 fraction too high",
                    "N2 flow rate < 2% of full scale (0.2 SLPM)",
                ],
            ),
            ("O2 2.6, N2 0", 2.6, 1, ["O2 flow rate > 2.5 SLPM"]),
            (
                "O2 11, N2 11",
                22,
                0.5,
                ["O2 flow rate > 2.5 SLPM", "N2 flow rate > 10 SLPM"],
            ),
            ("O2 0, N2 11", 11, 0, ["N2 flow rate > 10 SLPM"]),
            (
                "O2 0.001, N2 0.999",
                1,
                0.001,
                ["O2 flow rate < 2% of full scale (0.05 SLPM)"],
            ),
            (
                "O2 0.999, N2 0.001",
                1,
                0.999,
                ["N2 flow rate < 2% of full scale (0.2 SLPM)"],
            ),
        ],
    )
    def test_flags_expected_validation_errors(
        self, name, setpoint_total_flow_rate, setpoint_o2_fraction, expected_errors
    ):
        o2_source_gas_fraction = 1

        mix_validation_errors = module.get_mix_validation_errors(
            setpoint_total_flow_rate, o2_source_gas_fraction, setpoint_o2_fraction
        )

        assert set(mix_validation_errors) == set(expected_errors)


class TestStartConstantFlowMix:
    @pytest.mark.parametrize(
        "setpoint_o2_fraction", [0.1, 0.21, 0.1111, math.pi * 0.01]
    )
    def test_get_source_gas_flow_rates_ppb_adds_to_one_billion(
        self, setpoint_o2_fraction
    ):
        n2_ppb, o2_ppb = module._get_source_gas_flow_rates_ppb(
            o2_source_gas_o2_fraction=0.21, setpoint_o2_fraction=setpoint_o2_fraction
        )
        assert n2_ppb + o2_ppb == module._ONE_BILLION

    def test_turns_mixer_off_when_flow_rate_set_to_zero(self, mocker):
        mock_stop_flow = mocker.patch.object(module, "_stop_flow")

        module.start_constant_flow_mix_with_retry(
            sentinel.port,
            setpoint_flow_rate_slpm=0,
            setpoint_o2_fraction=1,
            o2_source_gas_o2_fraction=1,
        )

        mock_stop_flow.assert_called_once_with(sentinel.port)

    def test_calls_appropriate_sequence(self, mocker):
        # Most implementation details of this function are tested manually or verified by mypy.
        # This is just a smoke test
        mock_send_sequence = mocker.patch.object(
            module, "_send_sequence_with_expected_responses"
        )

        module.start_constant_flow_mix_with_retry(
            sentinel.port,
            setpoint_flow_rate_slpm=5,
            setpoint_o2_fraction=0.1,
            o2_source_gas_o2_fraction=0.5,
        )
        mock_send_sequence.assert_called_with(
            sentinel.port,
            [
                ("A MXRM 3", "A 3"),
                ("A MXMF 800000000 200000000", "A 800000000 200000000"),
                ("A MXRFF 5.00", "A 5.00 7 SLPM"),
                ("A MXRS 1", "A 2"),
            ],
        )

    def test_formats_requests_sensibly_even_when_ridiculous_fractions_requested(
        self, mocker
    ):
        mock_send_sequence = mocker.patch.object(
            module, "_send_sequence_with_expected_responses"
        )

        module.start_constant_flow_mix_with_retry(
            sentinel.port,
            setpoint_flow_rate_slpm=4.900000219837419237412374,
            setpoint_o2_fraction=0.100000111111111111111111111111111,
            o2_source_gas_o2_fraction=0.5000003129384612384761234981723,
        )
        mock_send_sequence.assert_called_with(
            sentinel.port,
            [
                ("A MXRM 3", "A 3"),
                ("A MXMF 799999903 200000097", "A 799999903 200000097"),
                ("A MXRFF 4.90", "A 4.90 7 SLPM"),
                ("A MXRS 1", "A 2"),
            ],
        )
