from unittest.mock import sentinel

import pytest

import calibration_environment.drivers.ysi as module

VALID_NUMBER_AS_BYTES = b"49.9"


class TestYSICommand:
    def test_response_parser_for_string_can_parse_real_value(self):
        response_payload = "OSMO%20YSI%20ODO%201"
        expected = "OSMO YSI ODO 1"
        assert (
            module.YSICommand.get_unit_id.response_payload_parser(response_payload)
            == expected
        )


class TestParseResponse:
    def test_parses_valid_response_using_payload_parser(self):
        valid_ysi_response = (
            module._YSI_RESPONSE_INITIATOR
            + VALID_NUMBER_AS_BYTES
            + module._YSI_RESPONSE_TERMINATOR
        )
        assert module.parse_response_packet(valid_ysi_response, float) == 49.9

    @pytest.mark.parametrize(
        "name, invalid_ysi_response, expected_error_message_content",
        [
            (
                "invalid terminator",
                module._YSI_RESPONSE_INITIATOR
                + VALID_NUMBER_AS_BYTES
                + b"get to da choppah",
                "terminator",
            ),
            (
                "invalid initiator",
                b"ohai" + VALID_NUMBER_AS_BYTES + module._YSI_RESPONSE_TERMINATOR,
                "initiator",
            ),
            (
                "can't be converted to expected response type",
                module._YSI_RESPONSE_INITIATOR
                + b"schwifty five"
                + module._YSI_RESPONSE_TERMINATOR,
                "float",
            ),
            ("empty", b"", None),
            ("weird garbage", b"$$$\r\n$ACK\r\n\r\n$ACK\r\n", None),
        ],
    )
    def test_blows_up_on_invalid_response(
        self, name, invalid_ysi_response, expected_error_message_content
    ):
        with pytest.raises(
            module.InvalidYsiResponse, match=expected_error_message_content
        ):
            module.parse_response_packet(invalid_ysi_response, payload_parser=float)


class TestGetSensorReading:
    def test_calls_serial_and_parses_response_appropriately(self, mocker):
        expected_sensor_value = 123.456
        mock_serial_interface = mocker.patch.object(
            module, "send_serial_command_and_get_response"
        )
        mock_serial_interface.return_value = b"$123.456\r\n$ACK\r\n"

        actual_sensor_value = module.get_sensor_reading_with_retry(
            sentinel.port, module.YSICommand.get_do_pct_sat
        )

        assert actual_sensor_value == expected_sensor_value
        mock_serial_interface.assert_called_once_with(
            port=sentinel.port,
            baud_rate=57600,
            command=b"$ADC Get Normal SENSOR_DO_PERCENT_SAT\r\n",
            response_terminator=module._YSI_RESPONSE_TERMINATOR,
            timeout=1,
        )


class TestGetStandardSensorValues:
    def test_reports_expected_values_including_partial_pressure(self, mocker):
        do_percent_saturation = 20.0
        barometric_pressure_mmhg = 700.0
        expected_do_partial_pressure_mmhg = 29.33
        do_partial_pressure_field_name = "DO (mmHg)"

        def fake_get_sensor_reading_with_retry(port, command):
            if command == module.YSICommand.get_do_pct_sat:
                return do_percent_saturation
            elif command == module.YSICommand.get_barometric_pressure_mmhg:
                return barometric_pressure_mmhg
            return sentinel.other_sensor_reading

        mocker.patch.object(
            module,
            "get_sensor_reading_with_retry",
            side_effect=fake_get_sensor_reading_with_retry,
        )

        sensor_values = module.get_standard_sensor_values(sentinel.port)

        assert do_partial_pressure_field_name in sensor_values
        assert (
            sensor_values[do_partial_pressure_field_name]
            == expected_do_partial_pressure_mmhg
        )
        assert (
            sensor_values[do_partial_pressure_field_name]
            == expected_do_partial_pressure_mmhg
        )

    def test_reports_unit_id(self, mocker):
        unit_id = "Bob"

        def fake_get_sensor_reading_with_retry(port, command):
            if command == module.YSICommand.get_unit_id:
                return unit_id
            # We have to return a number, not a sentinel, because the code does math with it
            return 5

        mocker.patch.object(
            module,
            "get_sensor_reading_with_retry",
            side_effect=fake_get_sensor_reading_with_retry,
        )

        sensor_values = module.get_standard_sensor_values(sentinel.port)

        assert sensor_values["Unit ID"] == unit_id
