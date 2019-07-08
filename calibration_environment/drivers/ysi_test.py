from unittest.mock import sentinel

import pytest

import calibration_environment.drivers.ysi as module


def _replace_char(original_bytes, index_to_replace, replace_with):
    """ Very brittle. Only use with indices explicitly tested below. Known to be broken when index_to_replace=-1"""
    if index_to_replace == -1:
        raise ValueError("Read the docstring plz.")

    return (
        original_bytes[:index_to_replace]
        + replace_with
        + original_bytes[index_to_replace + 1 :]
    )


class TestReplaceChar:
    @pytest.mark.parametrize(
        "char_to_replace, expected_result",
        [(0, b"62345"), (2, b"12645"), (-2, b"12365")],
    )
    def test_replaces_character(self, char_to_replace, expected_result):
        assert _replace_char(b"12345", char_to_replace, b"6") == expected_result


class TestParseYsiResponse:
    valid_ysi_response = b"$49.9\r\n$ACK\r\n"

    def test_parses_valid_response(self):
        assert module.parse_ysi_response(self.valid_ysi_response) == 49.9

    @pytest.mark.parametrize(
        "name, invalid_ysi_response, expected_error_message_content",
        [
            (
                "invalid terminator",
                _replace_char(valid_ysi_response, -2, b"X"),
                "terminator",
            ),
            (
                "invalid initiator",
                _replace_char(valid_ysi_response, 0, b"X"),
                "initiator",
            ),
            ("invalid float", _replace_char(valid_ysi_response, 1, b"X"), "float"),
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

        actual_sensor_value = module.get_sensor_reading(
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
