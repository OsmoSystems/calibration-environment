import logging
from typing import Optional

import serial

logger = logging.getLogger(__name__)


def send_serial_command_and_get_response(
    port: str,
    command: bytes,
    response_terminator: Optional[bytes] = None,
    max_response_bytes: Optional[int] = None,
    baud_rate: int = 19200,
    timeout: float = 0.1,
) -> bytes:
    """ Send a command on a serial port and return the response byte string

    Args:
        port: serial port to use, e.g. "COM11"
        command: byte string to send
        response_terminator: if provided, response listening will terminate on this string
        max_response_bytes: maximum number of bytes in the response.
            If provided, we'll only wait for this many characters in the response.
            If both response_terminator and max_response_bytes are provided,
                either condition can terminate the response (whichever one happens first).
        baud_rate: baud rate for serial connection
        timeout: timeout for serial connection in seconds. Default: 0.1. If timeout elapses
            while we're waiting for a response, we'll return whatever data we have.

    Returns:
        response byte string from the serial port

    Raises:
        serial.SerialException if serial port can't be opened
        ValueError if parameters are out of range, e.g. baud rate etc.
    """
    logger.debug(f"Serial command on {port}: {command!r}")

    with serial.Serial(port, baudrate=baud_rate, timeout=timeout) as connection:
        connection.write(command)
        response = (
            connection.read_until(response_terminator, max_response_bytes)
            if response_terminator
            else connection.read(max_response_bytes)
        )

    logger.debug(f"Serial response on {port}: {response}")

    return response
