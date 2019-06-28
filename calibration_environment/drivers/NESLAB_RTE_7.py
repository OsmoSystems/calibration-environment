import serial

"""
TODOs:
 - Polish docstrings
 - Manually test sending commands
 - Update turn on/off to enforce things like precision
 - Handle error responses from water bath
"""

"""
Excerpts from the datasheet:
(https://drive.google.com/open?id=1Tg-e1C8Ht8BE7AYzKVSqjw9bhWWxqKlz)

All data is sent and received in binary form, do not use ASCII. In the following
pages the binary data is represented in hexadecimal (hex) format.

The NC Serial Communications Protocol is based on a master-slave model.
The master is a host computer, while the slave is the bath's controller. Only
the master can initiate a communications transaction (half-duplex). The bath
ends the transaction by responding to the master’s query. The protocol uses
either an RS-232 or RS-485 serial interface with the default parameters: 19200
baud, 1 start bit, 8 data bits, 1 stop bit, no parity.

The framing of the communications packet in both directions is:

 - Lead char    RS-232 = CA (hex) RS-485 = CC (hex).
 - Addr-MSB     Most significant byte of device address. Always 0x00.
 - Addr-LSB     Least significant byte of device address
                    0x01 to 0x64 (1 - 100 decimal) for RS-485
                    0x01 for RS-232
 - Command      Command byte
 - n d-bytes    Number of data bytes to follow (0x00 to 0x08)
 - d-byte 1     1st data byte
 - ...
 - d-byte n     nth data byte
 - Checksum     Bitwise inversion of the 1 byte sum of bytes beginning with the most
                significant address byte and ending with the byte preceding the checksum.
                (To perform a bitwise inversion, XOR the one byte sum with 0xFF hex.

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


RS_485_PREFIX = 0xCC
RS_232_PREFIX = 0xCA

# We're using RS-232, which means the device address is always 0x00 0x01
DEFAULT_PREFIX = RS_232_PREFIX
DEFAULT_DEVICE_ADDRESS_MSB = 0x00
DEFAULT_DEVICE_ADDRESS_LSB = 0x01

# Default protocol settings on the NESLAB RTE. They can be reconfigured.
PROTOCOL_DEFAULTS = {
    "baudrate": 19200,
    "bytesize": serial.EIGHTBITS,
    "parity": serial.PARITY_NONE,
    "stopbits": serial.STOPBITS_ONE,
}

COMMAND_NAME_TO_HEX = {
    # Read Commands
    "Read Internal Temperature": 0x20,
    "Read External Sensor": 0x21,
    "Read Setpoint": 0x70,
    "Read Low Temperature Limit": 0x40,
    "Read High Temperature Limit": 0x60,
    "Read Heat Proportional Band": 0x71,
    "Read Heat Integral": 0x72,
    "Read Heat Derivative": 0x73,
    "Read Cool Proportional Band": 0x74,
    "Read Cool Integral": 0x75,
    "Read Cool Derivative": 0x76,
    # Set Commands
    "Set Setpoint": 0xF0,
    "Set Low Temperature Limit": 0xC0,
    "Set High Temperature Limit": 0xE0,
    "Set Heat Proportional Band": 0xF1,  # (P = 0.1-99.9)
    "Set Heat Integral": 0xF2,  # (I = 0-9.99)
    "Set Heat Derivative": 0xF3,  # (D = 0-5.0)
    "Set Cool Proportional Band": 0xF4,  # (P = 0.1-99.9)
    "Set Cool Integral": 0xF5,  # (I = 0-9.99)
    "Set Cool Derivative": 0xF6,  # (D = 0-5.0)
    # Exclude these as they have non-generic responses - handle them one-off:
    # "Read Acknowledge": 0x00,
    # "Read Status": 0x09,
    # "Set On/Off Array": 0x81,
}


QUALIFIER_HEX_TO_PRECISION = {
    0x10: 0.1,
    0x20: 0.01,
    0x11: 0.1,  # Units: degrees C
    0x21: 0.01,  # Units: degrees C
}


class SerialPacket:
    """
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
                (To perform a bitwise inversion, XOR the one byte sum with 0xFF hex.
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

    def __repr__(self):
        return str(self.__dict__)

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
        try:
            assert self._prefix == DEFAULT_PREFIX
            assert self._device_address_msb == DEFAULT_DEVICE_ADDRESS_MSB
            assert self._device_address_lsb == DEFAULT_DEVICE_ADDRESS_LSB
            assert len(self.data_bytes) == self._data_bytes_count
            assert _calculate_checksum(self._message_bytes) == self._checksum
        except AssertionError:
            # TODO: could do something fancier here to get more useful error messages.
            raise ValueError(f"Serial packet ({str(self)}) invalid.")


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


def _parse_data_bytes_as_float(qualified_data_bytes: bytes) -> float:
    """ Parse data bytes into an float value with appropriate precision.

        From the datasheet:
            When the bath sends data, a qualifier byte is sent first, followed by a two
            byte signed integer (16 bit, MSB sent first). The qualifier byte indicates
            the precision and units of measure for the requested data as detailed in
            Table 2.

        Table 2 is recorded in QUALIFIER_HEX_TO_PRECISION.

        e.g. a temperature value of 62.5°C would be sent as b"\x11\x02\x71"
            The qualifier byte of 11 indicates a precision of 1 decimal point and units
            of °C. The temperature of 62.5°C is 625 decimal = 271 hex.
    """
    qualifier = qualified_data_bytes[0]
    data_bytes = qualified_data_bytes[1:]

    precision = QUALIFIER_HEX_TO_PRECISION[qualifier]

    return int.from_bytes(data_bytes, byteorder="big") * precision


def _send_command(comm_port: str, command_packet_bytes: bytes):
    with serial.Serial(comm_port, timeout=0.1, **PROTOCOL_DEFAULTS) as serial_port:
        serial_port.write(command_packet_bytes)
        response_bytes = serial_port.readline()
        return SerialPacket.from_bytes(response_bytes)


def _construct_command_packet(command_name: str, data: int = None):
    if data is None:
        # Read commands don't include data
        data_bytes = b""
    else:
        # Set commands' data is always multiplied by 10 to include 1 decimal of precision, and
        # always sent as two bytes
        data_as_10x_int = round(data * 10)
        data_byte_count = 2
        data_bytes = data_as_10x_int.to_bytes(data_byte_count, byteorder="big")

    command = COMMAND_NAME_TO_HEX[command_name]

    return SerialPacket.from_command(command, data_bytes)


def send_command_and_parse_response(comm_port, command_name: str, data: float = None):
    """ Send a generic command to the water bath and parse the response data
    """

    command_serial_packet = _construct_command_packet(command_name, data)
    response_packet = _send_command(comm_port, command_serial_packet.to_bytes())

    # TODO: handle error response from bath

    return _parse_data_bytes_as_float(response_packet.data_bytes)


# TODO: probably change this to a generic "initialize" function
def turn_on(comm_port):
    """ The "Set On/Off" command has a unique data structure in which each data byte
        represents a single setting that can be toggled (including turning on/off the
        bath). This function just turns on the water bath and doesn't change any other
        settings.

        Command and response format: CA 00 01 81 08 (d1)...(d8)(cs)
        Data bytes meaning:
            (di: 0 = off, 1 = on, 2 = no change)
            d1 = unit on/off
            d2 = sensor enable
            d3 = faults enabled
            d4 = mute
            d5 = auto restart
            d6 = 0.01°C enable  # TODO: we could ensure that the precision is either 0.1 or 0.01 C using this command
            d7 = full range cool enable
            d8 = serial comm enable

        To just turn on and change nothing else:
            CA 00 01 81 08 01 02 02 02 02 02 02 02 66
    """

    # Hardcoded to turn on bath and change nothing else
    data_bytes = bytes.fromhex("01 02 02 02 02 02 02 02")
    command_packet_bytes = SerialPacket.from_command(
        command=0x81, data_bytes=data_bytes
    )
    response_packet = _send_command(comm_port, command_packet_bytes)

    # TODO: parse the response to check that it turned on?
    return response_packet
