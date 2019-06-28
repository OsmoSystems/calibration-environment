import collections

import serial


"""
A driver for the Thermo Scientific NESLAB RTE 7 Temperature-controlled water bath

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
    # Exclude these from the dictionary of commands as they have non-generic responses
    # Handle them one-off as necessary
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


class InvalidResponse(ValueError):
    pass


class ErrorResponse(ValueError):
    pass


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

    def __str__(self):
        bytes_as_hex = f" ".join((f"0x{byte:02X}" for byte in self.to_bytes()))
        return f"bytes: {bytes_as_hex}, attributes: {str(self.__dict__)}"

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
                f"Serial packet invalid.\n Errors: {errors}.\n Packet: {self}"
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


ERROR_RESPONSE_COMMAND = 0x0F


def _check_for_error_response(serial_packet: SerialPacket):
    if serial_packet.command == ERROR_RESPONSE_COMMAND:
        error_type = serial_packet.data_bytes[0]
        echoed_command = serial_packet.data_bytes[1]

        error_types = {0x01: "Bad Command", 0x03: "Bad Checksum"}

        error = error_types.get(error_type, "Unknown")

        raise ErrorResponse(
            f"Bath responded with error response."
            f"Error: {error}. "
            f"Echo of command byte as received: 0x{echoed_command:02X}."
        )


def _send_command(port: str, command_packet: SerialPacket):
    """ Send command packet bytes to the bath and collect response
    """
    with serial.Serial(port, timeout=0.1, **PROTOCOL_DEFAULTS) as serial_port:
        serial_port.write(command_packet.to_bytes())

        # Use read() instead of readline() as the bath can sometime send bytes that get
        # interpreted as EOL characters. Set it to read `more_than_enough_bytes` so that
        # it definitely gets all the bytes in the respose (longest message is 14 bytes)
        # and only stops at the timeout
        more_than_enough_bytes = 20
        response_bytes = serial_port.read(more_than_enough_bytes)

        try:
            serial_packet = SerialPacket.from_bytes(response_bytes)
        except Exception as e:
            raise InvalidResponse(
                f"Unable to parse response from water bath."
                f"Response bytes: {response_bytes}"
                f"Error: {str(e)}"
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
        precision = 0.1  # Assumes the bath has already been set to use this precision

        data_byte_count = 2  # Data is always sent as two bytes

        data_bytes = round(data / precision).to_bytes(data_byte_count, byteorder="big")

    command = COMMAND_NAME_TO_HEX[command_name]

    return SerialPacket.from_command(command, data_bytes)


def send_command_and_parse_response(port: str, command_name: str, data: float = None):
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
    response_packet = _send_command(port, command_packet)

    return _parse_data_bytes_as_float(response_packet.data_bytes)


"""
The "Set On/Off Array" command has a unique data structure in which each data byte
represents a single setting that can be toggled (including turning on/off the
bath).

Command and response format: CA 00 01 81 08 (d1)...(d8)(cs)
Data bytes meaning:
    (di: 0 = off, 1 = on, 2 = no change)
    d1 = unit on/off
    d2 = sensor enable
    d3 = faults enabled
    d4 = mute
    d5 = auto restart
    d6 = 0.01°C enable
    d7 = full range cool enable
    d8 = serial comm enable

e.g. to just turn on and change nothing else:
    CA 00 01 81 08 01 02 02 02 02 02 02 02 66
"""
OFF = 0
ON = 1
NO_CHANGE = 2  # Don't change the current bath setting

OnOffArraySettings = collections.namedtuple(
    "OnOffArraySettings",
    [
        "unit_on_off",  # Turn unit on/off. ON: Turn it on. OFF: Turn it off
        "external_sensor_enable",  # ON: Use external sensor. OFF: Use internal sensor
        "faults_enabled",  # Behavior when faults encountered. ON: Shut down. OFF: Continue to run.
        "mute",
        "auto_restart",
        "high_precision_enable",  # Use 0.01 C precision. ON: Use 0.01 C. OFF: Use 0.1 C.
        "full_range_cool_enable",
        "serial_comm_enable",  # Serial communication. ON: Use serial communication. OFF: use local
    ],
)

DEFAULT_ON_OFF_ARRAY_SETTINGS = OnOffArraySettings(
    unit_on_off=ON,  # Turn on unit
    external_sensor_enable=ON,  # Use external sensor
    faults_enabled=NO_CHANGE,
    mute=NO_CHANGE,
    auto_restart=NO_CHANGE,
    high_precision_enable=OFF,  # Use 0.1 C precision
    full_range_cool_enable=NO_CHANGE,
    serial_comm_enable=ON,  # Control bath using serial communications
)

SET_ON_OFF_ARRAY_COMMAND = 0x81


def _construct_settings_command_packet() -> SerialPacket:
    """ Construct a command packet to set on/off settings to desired, hardcoded values
    """
    return SerialPacket.from_command(
        command=SET_ON_OFF_ARRAY_COMMAND,
        data_bytes=bytes(DEFAULT_ON_OFF_ARRAY_SETTINGS),
    )


def _parse_settings_data_bytes(settings_data_bytes: bytes) -> OnOffArraySettings:
    """ Parse data_bytes from the bath's response to a "Set On/Off Array" command
    """
    return OnOffArraySettings(*settings_data_bytes)


def _validate_settings(settings: OnOffArraySettings):
    checks = {
        "Water bath isn't turned on": settings.unit_on_off == ON,
        "External sensor isn't enabled": settings.external_sensor_enable == ON,
        "Precision isn't 0.1 C": settings.high_precision_enable == OFF,
        "Serial comms aren't enabled": settings.serial_comm_enable == ON,
    }
    errors = [error_message for error_message, check in checks.items() if not check]
    if errors:
        raise ValueError(errors)


def initialize(port: str) -> None:
    """ Ensure that the water bath is turned on and that its settings are initialized
        as we expect by sending a set settings command.

        Args:
            port: The comm port used by the water bath
    """
    settings_command_packet = _construct_settings_command_packet()
    response_packet = _send_command(port, settings_command_packet)

    response_settings = _parse_settings_data_bytes(response_packet.data_bytes)

    _validate_settings(response_settings)

    # TODO: return something here?
