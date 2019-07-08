from unittest.mock import sentinel

import pytest

import calibration_environment.drivers.serial_port as module


@pytest.fixture
def mock_serial_class_and_connection(mocker):
    mock_serial_class = mocker.patch.object(module.serial, "Serial")
    mock_connection = mocker.Mock()
    mock_serial_class.return_value.__enter__.return_value = mock_connection
    return mock_serial_class, mock_connection


class TestSendSerialCommandAndGetResponse:
    def test_sets_up_connection_and_sends_command_appropriately(
        self, mock_serial_class_and_connection
    ):
        mock_serial_class, mock_connection = mock_serial_class_and_connection

        module.send_serial_command_and_get_response(
            port=sentinel.port,
            command=sentinel.command,
            response_terminator=sentinel.response_terminator,
            max_response_bytes=sentinel.max_response_bytes,
            baud_rate=sentinel.baud_rate,
            timeout=sentinel.timeout,
        )

        mock_serial_class.assert_called_with(
            sentinel.port, baudrate=sentinel.baud_rate, timeout=sentinel.timeout
        )
        mock_connection.write.assert_called_with(sentinel.command)

    def test_with_terminator_and_response_bytes_returns_result_using_read_until(
        self, mock_serial_class_and_connection
    ):
        mock_serial_class, mock_connection = mock_serial_class_and_connection
        mock_connection.read_until.return_value = sentinel.response_bytes

        actual_response = module.send_serial_command_and_get_response(
            port=sentinel.port,
            command=sentinel.command,
            response_terminator=sentinel.response_terminator,
            max_response_bytes=sentinel.max_response_bytes,
            baud_rate=sentinel.baud_rate,
            timeout=sentinel.timeout,
        )

        mock_connection.read_until.assert_called_with(
            sentinel.response_terminator, sentinel.max_response_bytes
        )

        assert actual_response == sentinel.response_bytes

    def test_without_terminator_returns_result_using_read(
        self, mock_serial_class_and_connection
    ):
        mock_serial_class, mock_connection = mock_serial_class_and_connection
        mock_connection.read.return_value = sentinel.response_bytes

        actual_response = module.send_serial_command_and_get_response(
            port=sentinel.port,
            command=sentinel.command,
            # No response terminator here!
            max_response_bytes=sentinel.max_response_bytes,
            baud_rate=sentinel.baud_rate,
            timeout=sentinel.timeout,
        )

        mock_connection.read.assert_called_with(sentinel.max_response_bytes)

        assert actual_response == sentinel.response_bytes

    def test_logs_request_and_response_at_debug_level(
        self, mocker, mock_serial_class_and_connection
    ):
        mock_debug_logger = mocker.patch.object(module.logger, "debug")
        mock_serial_class, mock_connection = mock_serial_class_and_connection
        mock_connection.read.return_value = sentinel.response_bytes

        module.send_serial_command_and_get_response(
            port=sentinel.port,
            command=sentinel.command,
            max_response_bytes=sentinel.max_response_bytes,
            baud_rate=sentinel.baud_rate,
            timeout=sentinel.timeout,
        )

        mock_debug_logger.assert_has_calls(
            [
                mocker.call("Serial command on sentinel.port: sentinel.command"),
                mocker.call(
                    "Serial response on sentinel.port: sentinel.response_bytes"
                ),
            ]
        )
