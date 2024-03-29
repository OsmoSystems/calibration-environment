# Serial communications protocol for the NESLAB RTE 17 temperature-controlled water bath
from calibration_environment.drivers.serial_port import (
    send_serial_command_and_get_response,
)
from calibration_environment.drivers.water_bath.constants import (
    DEFAULT_PREFIX,
    DEFAULT_DEVICE_ADDRESS_MSB,
    DEFAULT_DEVICE_ADDRESS_LSB,
    _QUALIFIER_HEX_TO_PRECISION,
    ERROR_RESPONSE_COMMAND,
    DEFAULT_BAUD_RATE,
    REPORTING_PRECISION,
    COMMAND_NAME_TO_HEX,
)
from calibration_environment.drivers.water_bath.exceptions import (
    PrecisionMismatch,
    ErrorResponse,
    InvalidResponse,
)

"""
General serial communications notes:

All data is sent and received in binary form, do not use ASCII. In the following
pages the binary data is represented in hexadecimal (hex) format.

The NC Serial Communications Protocol is based on a master-slave model.
The master is a host computer, while the slave is the bath's controller. Only
the master can initiate a communications transaction (half-duplex). The bath
ends the transaction by responding to the master’s query. The protocol uses
either an RS-232 or RS-485 serial interface with the default parameters: 19200
baud, 1 start bit, 8 data bits, 1 stop bit, no parity.

(See SerialPacket for the framing of the communications packet)

The master requests information by sending one of the Read Functions. Since no data is
sent to the bath during a read request, the master uses 00 for the number of data bytes
following the command byte.

The bath will respond to a Read Function by echoing the lead character, address, and
command byte, followed by the requested data and checksum. When the bath sends data, a
qualifier byte is sent first, followed by a two byte signed integer (16 bit, MSB sent
first). The qualifier byte indicates the precision and units of measure for the
requested data as detailed in Table 2.

The master sets parameters in the bath by sending one of the Set Functions. The master
does not send a qualifier byte in the data field. The master should be pre-programmed to
send the correct precision and units (it could also read the parameter of interest first
to decode the correct precision and units needed).

"""


class SerialPacket:
    """
    From the datasheet:

    The framing of the communications packet in both directions is:

    Prefix      0xCA (RS-232); or 0xCC (RS-485)
    Addr-MSB    Most significant byte of device address. Always 0x00.
    Addr-LSB    Least significant byte of device address
                    0x01 to 0x64 (1 - 100 decimal) for RS-485
                    0x01 for RS-232
    Command     Command byte
    n d-bytes   Number of data bytes to follow (0x00 to 0x08)
    d-byte 1    1st data byte
    ...
    d-byte n    nth data byte
    Checksum    Bitwise inversion of the 1 byte sum of bytes beginning with the most
                significant address byte and ending with the byte preceding the checksum.
                To perform a bitwise inversion, XOR the one byte sum with 0xFF hex.
    """

    def __init__(
        self,
        prefix: int,
        device_address_msb: int,
        device_address_lsb: int,
        command: int,
        data_bytes_count: int,
        data_bytes: bytes,
        checksum: int = None,
    ):
        self._prefix = prefix
        self._device_address_msb = device_address_msb
        self._device_address_lsb = device_address_lsb
        self.command = command
        self._data_bytes_count = data_bytes_count
        self.data_bytes = data_bytes

        self._checksum = (
            checksum
            if checksum is not None
            else _calculate_checksum(self._message_bytes)
        )

        self.validate()

    def _bytes_as_hex_str(self):
        return " ".join((f"0x{byte:02X}" for byte in self.to_bytes()))

    def __str__(self):
        return f"bytes: {self._bytes_as_hex_str()}, attributes: {str(self.__dict__)}"

    def __repr__(self):
        # object.__repr__() produces something like <Foo object at 0x12425>. We want to keep that information in our
        # final result (including the ID - so just start with object repr and strip off the right-side bracket
        repr_without_closing_bracket = object.__repr__(self).rstrip(">")
        return f"{repr_without_closing_bracket}. bytes: {self._bytes_as_hex_str()}>"

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    @classmethod
    def from_bytes(cls, packet_bytes: bytes):
        """ Constructs a SerialPacket by parsing a byte string (e.g. a response from the
            water bath)
        """

        return cls(
            prefix=packet_bytes[0],
            device_address_msb=packet_bytes[1],
            device_address_lsb=packet_bytes[2],
            command=packet_bytes[3],
            data_bytes_count=packet_bytes[4],
            data_bytes=packet_bytes[5:-1],
            checksum=packet_bytes[-1],
        )

    @classmethod
    def from_command(cls, command: int, data_bytes: bytes = bytes([])):
        """ Constructs a SerialPacket based around a command and the desired data to be
            sent with that command
        """
        return cls(
            prefix=DEFAULT_PREFIX,
            device_address_msb=DEFAULT_DEVICE_ADDRESS_MSB,
            device_address_lsb=DEFAULT_DEVICE_ADDRESS_LSB,
            command=command,
            data_bytes_count=len(data_bytes),
            data_bytes=data_bytes,
        )

    def to_bytes(self):
        return bytes([self._prefix]) + self._message_bytes + bytes([self._checksum])

    @property
    def _message_bytes(self):
        """ Everything except first (prefix) and last (checksum) byte.
            Used to compute checksum
        """
        return (
            bytes([self._device_address_msb, self._device_address_lsb])
            + bytes([self.command])
            + bytes([self._data_bytes_count])
            + self.data_bytes
        )

    def validate(self):
        checks = (
            # (name, actual, expected)
            ("prefix", self._prefix, DEFAULT_PREFIX),
            ("addr msb", self._device_address_msb, DEFAULT_DEVICE_ADDRESS_MSB),
            ("addr lsb", self._device_address_lsb, DEFAULT_DEVICE_ADDRESS_LSB),
            ("data bytes count", self._data_bytes_count, len(self.data_bytes)),
            ("checksum", self._checksum, _calculate_checksum(self._message_bytes)),
        )
        errors = [
            f"{check_name} actual ({actual}) != expected ({expected})"
            for check_name, actual, expected in checks
            if actual != expected
        ]

        if errors:
            raise ValueError(
                f"\nSerial packet invalid. \nErrors: {errors}. \nPacket: {self}"
            )


def _calculate_checksum(message_bytes: bytes) -> int:
    """ Calculate the checksum of the "message bytes" of a serial packet

        From the datasheet, the checksum is:
            Bitwise inversion of the 1 byte sum of bytes beginning with the most
            significant address byte and ending with the byte preceding the checksum.
            To perform a bitwise inversion, "exclusive OR" the one byte sum with FF hex.

        Args:
            message_bytes: everything except the first (prefix) and last (checksum) byte
            in the packet.

        Returns:
            The checksum
    """
    least_signficiant_byte_of_sum = sum(message_bytes) & 0xFF
    bitwise_inversion = least_signficiant_byte_of_sum ^ 0xFF
    return bitwise_inversion


def _validate_precision_matches(precision, expected_precision):
    """ Validate that the precision sent back by the bath is the same precision we're
        using to send data.
    """
    if precision != expected_precision:
        raise PrecisionMismatch(
            f"\nThe precision reported by the bath ({precision}) doesn't match "
            f"the precision we're using to send data ({expected_precision})."
            f"\nRun initialize() to set the bath to use our desired precision."
        )


def _parse_data_bytes_as_float(
    qualified_data_bytes: bytes, expected_precision: float
) -> float:
    """ Parse data bytes into a float value with appropriate precision.

        From the datasheet:
            When the bath sends data, a qualifier byte is sent first, followed by a two
            byte signed integer (16 bit, MSB sent first). The qualifier byte indicates
            the precision and units of measure for the requested data as detailed in
            Table 2.

        Table 2 is recorded in _QUALIFIER_HEX_TO_PRECISION.

        e.g. a temperature value of 62.5°C would be sent as b"\x11\x02\x71"
            The qualifier byte of 11 indicates a precision of 1 decimal point and units
            of °C. The temperature of 62.5°C is 625 decimal = 271 hex.
    """
    qualifier = qualified_data_bytes[0]
    data_bytes = qualified_data_bytes[1:]

    precision = _QUALIFIER_HEX_TO_PRECISION[qualifier]

    _validate_precision_matches(precision, expected_precision)

    return int.from_bytes(data_bytes, byteorder="big") * precision


def _check_for_error_response(serial_packet: SerialPacket):
    if serial_packet.command == ERROR_RESPONSE_COMMAND:
        error_type = serial_packet.data_bytes[0]
        echoed_command = serial_packet.data_bytes[1]

        error_types = {0x01: "Bad Command", 0x03: "Bad Checksum"}

        error = error_types.get(error_type, "Unknown")

        raise ErrorResponse(
            f"\nBath responded with error response. "
            f"\nSerial packet: {serial_packet}. "
            f"\nError: {error}. "
            f"\nEcho of command byte as received: 0x{echoed_command:02X}."
        )


def send_command(port: str, command_packet: SerialPacket) -> SerialPacket:
    """ Send command packet bytes to the bath and collect response
    """

    # longest message is 14 bytes: there's no consistent termination character in the water bath response,
    # so use this to always listen until the timeout.
    more_than_enough_bytes = 20

    response_bytes = send_serial_command_and_get_response(
        port=port,
        command=command_packet.to_bytes(),
        max_response_bytes=more_than_enough_bytes,
        baud_rate=DEFAULT_BAUD_RATE,
        timeout=0.1,
    )

    try:
        serial_packet = SerialPacket.from_bytes(response_bytes)
    except Exception as e:
        raise InvalidResponse(
            f"\nUnable to parse response from water bath. "
            f"\nResponse bytes: {response_bytes!r}. "
            f"\nError: {e}. "
            f"\nPossible solution: ensure the bath is in 'serial communication' mode"
        )

    _check_for_error_response(serial_packet)

    return serial_packet


def _construct_command_packet(command_name: str, data: float = None):
    if data is None:
        # Read commands don't include data
        data_bytes = b""
    else:
        # Set commands' data is divided by the desired decimal precision (0.1 or 0.01)
        # so that it can be sent as an int (the operation is reversed on the other side)
        # Assumes the bath has already been set to use the REPORTING_PRECISION

        data_byte_count = 2  # Data is always sent as two bytes

        # Convert explicitly to stdlib int in case the source is a numpy type
        # (numpy floats don't have .to_bytes() and round() doesn't coerce them to ints)
        data_bytes = int(round(data / REPORTING_PRECISION)).to_bytes(
            data_byte_count, byteorder="big"
        )

    command = COMMAND_NAME_TO_HEX[command_name]

    return SerialPacket.from_command(command, data_bytes)


def send_command_and_parse_response(
    port: str, command_name: str, data: float = None
) -> float:
    """ Send a generic command to the water bath and parse the response data

        Args:
            port: The comm port used by the water bath
            command_name: The name of the command to execute. See COMMAND_NAME_TO_HEX for options
            data: Optional. For Set commands: the desired setpoint value. For Read commands: None

        Returns:
            For Read commands: the actual value
            For Set commands: echos the requested setpoint value
    """

    command_packet = _construct_command_packet(command_name, data)
    response_packet = send_command(port, command_packet)

    return _parse_data_bytes_as_float(response_packet.data_bytes, REPORTING_PRECISION)
