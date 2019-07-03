import logging
from typing import Optional

import serial

logger = logging.getLogger(__name__)


def send_serial_command_and_get_response(
    port: str,
    command: bytes,
    response_terminator: Optional[bytes] = None,
    n_bytes: Optional[int] = None,
    baud_rate: int = 19200,
    timeout: float = 0.1,
) -> bytes:
    """ Send a command on a serial port and return the response byte string

    Args:
        port: serial port to use, e.g. "COM11"
        command: byte string to send
        response_terminator: terminator to
        n_bytes: maximum number of bytes in the response.
            If provided, we'll only wait for this many characters in the response
        baud_rate: baud rate for serial connection
        timeout: timeout for serial connection. Default: 0.1

    Returns:
        byte string of response on the serial port

    Raises:
        various exceptions raised by serial.Serial if serial port is not ready
    """
    if response_terminator is not None and n_bytes is not None:
        raise ValueError("")

    logger.debug(f"Serial command on {port}: {command}")

    with serial.Serial(port, baud_rate=baud_rate, timeout=timeout) as connection:
        connection.write(command)
        response = (
            connection.read_until(response_terminator, n_bytes)
            if response_terminator
            else connection.read(n_bytes)
        )

    logger.debug(f"Serial response on {port}: {response}")

    return response
