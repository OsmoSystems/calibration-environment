from unittest.mock import sentinel

import calibration_environment.drivers.ysi as module


class TestParseYsiResponse:
    def test_parses_response(self):
        assert module.parse_ysi_response("$49.9..$ACK..") == 49.9


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
            response_terminator=module.YSI_RESPONSE_TERMINATOR,
            timeout=1,
        )
