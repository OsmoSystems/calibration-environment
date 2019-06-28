import serial

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
baud, 1 start bit, 8 data bits, 1 stop bit, no parity, and for RS-485 a selectable
address from 1 to 100.

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
PREFIX = RS_232_PREFIX
DEVICE_ADDRESS_MSB = 0x00
DEVICE_ADDRESS_LSB = 0x01

# Default protocol settings on the NESLAB RTE. They can be reconfigured.
RS_232_PROTOCOL_DEFAULTS = {
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
    "Read Heat Proportional Band (P)": 0x71,
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
    # Exclude these as they have non-generic repsponses - handle them one-off:
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


class ResponsePacket:
    """
    The framing of the communications packet in both directions is:

    Lead char   0xCA (RS-232); or 0xCC (RS-485)
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

    def __init__(self, response_bytes):
        self.response_bytes: bytes = response_bytes
        self.prefix: int = response_bytes[0]
        self.device_address_msb: int = response_bytes[1]
        self.device_address_lsb: int = response_bytes[2]
        self.command: int = response_bytes[3]
        self.data_bytes_count: int = response_bytes[4]
        self.data_bytes: bytes = response_bytes[5:-1]
        self.checksum: int = response_bytes[-1]

        # TODO: torn about object-oriented vs. functional. Validate method inside constructor or as a separate function?
        self.validate()

    def validate(self):
        try:
            assert self.prefix == PREFIX
            assert self.device_address_msb == DEVICE_ADDRESS_MSB
            assert self.device_address_lsb == DEVICE_ADDRESS_LSB
            assert len(self.data_bytes) == self.data_bytes_count
            assert calculate_checksum(self.response_bytes[1:-1]) == self.checksum
        except AssertionError:
            # TODO: could do something fancier here to get more useful error messages.
            raise ValueError(f"Reponse packet ({self.response_bytes}) invalid.")


def calculate_checksum(message_bytes: bytes):
    """ Calculate the checksum of the "message bytes"

        From the datasheet, the checksum is:
            Bitwise inversion of the 1 byte sum of bytes beginning with the most
            significant address byte and ending with the byte preceding the checksum.
            To perform a bitwise inversion, "exclusive OR" the one byte sum with FF hex.

        Args:
            message_bytes: everything except the first (prefix) and last (checksum) byte in the packet.

        Returns:
            The checksum
    """
    least_signficiant_byte_of_sum = sum(message_bytes) & 0xFF
    bitwise_inversion = least_signficiant_byte_of_sum ^ 0xFF
    return bitwise_inversion


# TODO: could make or share a class for the command packet as well?
def construct_command_packet(command: int, data_bytes: bytes = bytes([])):
    data_bytes_count = len(data_bytes)

    message_bytes = (
        bytes([DEVICE_ADDRESS_MSB, DEVICE_ADDRESS_LSB])
        + bytes([command])
        + bytes([data_bytes_count])
        + data_bytes
    )

    checksum = calculate_checksum(message_bytes)

    return bytes([PREFIX]) + message_bytes + bytes([checksum])


def parse_data_bytes_as_float(qualified_data_bytes: bytes) -> float:
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
    with serial.Serial(comm_port, timeout=1, **RS_232_PROTOCOL_DEFAULTS) as serial_port:
        serial_port.write(command_packet_bytes)
        response_bytes = serial_port.readline()
        return ResponsePacket(response_bytes)


def send_command_and_parse_response(comm_port, command_name, data: float = None):
    """ Send a generic command to the water bath and parse the response data
    """

    # Command data is always multiplied by 10 to include 1 decimal of precision and sent
    # as two bytes
    # TODO: I think the command data might actually need to change to match whatever
    # precision the device is using (either 0.1 or 0.01)
    data_bytes = (
        round(data * 10).to_bytes(2, byteorder="big") if data is not None else b""
    )
    command = COMMAND_NAME_TO_HEX[command_name]
    command_packet_bytes = construct_command_packet(command, data_bytes)
    response_packet = _send_command(comm_port, command_packet_bytes)

    # TODO: handle error response from bath

    return parse_data_bytes_as_float(response_packet.data_bytes)


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
    command_packet_bytes = construct_command_packet(command=0x81, data_bytes=data_bytes)
    response_packet = _send_command(comm_port, command_packet_bytes)

    # TODO: parse the response to check that it turned on?
    return response_packet
