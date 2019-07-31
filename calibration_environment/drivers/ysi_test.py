from unittest.mock import sentinel

import pytest

import calibration_environment.drivers.ysi as module


class TestParseYsiResponse:
    valid_number = b"49.9"

    def test_parses_valid_response(self):
        valid_ysi_response = (
            module._YSI_RESPONSE_INITIATOR
            + self.valid_number
            + module._YSI_RESPONSE_TERMINATOR
        )
        assert module.parse_ysi_response(valid_ysi_response) == 49.9

    @pytest.mark.parametrize(
        "name, invalid_ysi_response, expected_error_message_content",
        [
            (
                "invalid terminator",
                module._YSI_RESPONSE_INITIATOR + valid_number + b"get to da choppah",
                "terminator",
            ),
            (
                "invalid initiator",
                b"ohai" + valid_number + module._YSI_RESPONSE_TERMINATOR,
                "initiator",
            ),
            (
                "invalid float",
                module._YSI_RESPONSE_INITIATOR
                + b"schwifty five"
                + module._YSI_RESPONSE_TERMINATOR,
                "float",
            ),
            ("empty", b"", None),
            ("weird garbage", b"$$$\r\n$ACK\r\n\r\n$ACK\r\n", None),
        ],
    )
    def test_blows_up_if_response_terminator_invalid(
        self, name, invalid_ysi_response, expected_error_message_content
    ):
        with pytest.raises(
            module.InvalidYsiResponse, match=expected_error_message_content
        ):
            module.parse_ysi_response(invalid_ysi_response)


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
    def test_reports_partial_pressure(self, mocker):
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
