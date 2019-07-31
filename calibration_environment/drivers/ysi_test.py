from unittest.mock import sentinel

import pytest

import calibration_environment.drivers.ysi as module


# TODO test DO mmHg functionality


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
