import serial


RS_485_PREFIX = 0xCC
RS_232_PREFIX = 0xCA

# We're using RS-232, which means the device address is always 0x00 0x01
PREFIX = RS_232_PREFIX
DEVICE_ADDRESS_MSB = 0x00
DEVICE_ADDRESS_LSB = 0x01

COMMAND_NAME_TO_HEX = {
    # "Read Acknowledge": 0x00,
    # "Read Status": 0x09,
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
    "Set Setpoint": 0xF0,
    "Set Low Temperature Limit**": 0xC0,
    "Set High Temperature Limit**": 0xE0,
    "Set Heat Proportional Band": 0xF1,  # (P = 0.1-99.9)
    "Set Heat Integral": 0xF2,  # (I = 0-9.99)
    "Set Heat Derivative": 0xF3,  # (D = 0-5.0)
    "Set Cool Proportional Band": 0xF4,  # (P = 0.1-99.9)
    "Set Cool Integral": 0xF5,  # (I = 0-9.99)
    "Set Cool Derivative": 0xF6,  # (D = 0-5.0)
    # "Set On/Off Array": 0x81,
}


QUALIFIER_HEX_TO_PRECISION = {
    0x10: 0.1,
    0x20: 0.01,
    0x11: 0.1,  # Units: degrees C
    0x21: 0.01,  # Units: degrees C
}


def _calculate_checksum(message_bytes):
    """ Sum the bytes, choose the least significant byte, and perform a bitwise inversion """
    least_signficiant_byte_of_sum = sum(message_bytes) & 0xFF
    bitwise_inversion = least_signficiant_byte_of_sum ^ 0xFF
    return bitwise_inversion


assert _calculate_checksum(b"\x00\x01\x00\x00") == 0xFE
assert _calculate_checksum(b"\x00\x01\x09\x00") == 0xF5


def construct_command_packet(command, data_bytes_count=0, data=None):
    data_bytes = (
        (data * 10).to_bytes(data_bytes_count, byteorder="big")
        if data is not None
        else b""
    )

    message_bytes = (
        bytes([DEVICE_ADDRESS_MSB, DEVICE_ADDRESS_LSB])
        + bytes([COMMAND_NAME_TO_HEX[command]])
        + bytes([data_bytes_count])
        + data_bytes
    )

    checksum = _calculate_checksum(message_bytes)

    return bytes([PREFIX]) + message_bytes + bytes([checksum])


def _validate_response(response_bytes, command):
    assert response_bytes[0] == PREFIX
    assert response_bytes[1] == DEVICE_ADDRESS_MSB
    assert response_bytes[2] == DEVICE_ADDRESS_LSB
    assert response_bytes[3] == COMMAND_NAME_TO_HEX[command]

    data_bytes_count = response_bytes[4]
    if data_bytes_count > 0:
        data_bytes = response_bytes[5:-1]
        assert len(data_bytes) == data_bytes_count

    response_checksum = response_bytes[-1]
    calculated_checksum = _calculate_checksum(response_bytes[1:-1])
    assert calculated_checksum == response_checksum


def _parse_decimal_data_bytes(qualified_data_bytes):
    qualifier_hex = qualified_data_bytes[0]
    precision = QUALIFIER_HEX_TO_PRECISION[qualifier_hex]

    data_bytes = qualified_data_bytes[1:]
    data = int.from_bytes(data_bytes, byteorder="big") * precision
    return data


def parse_response(response_bytes, command):
    _validate_response(response_bytes, command)
    data_bytes = response_bytes[5:-1]

    data = _parse_decimal_data_bytes(data_bytes)
    return data


def set(command_name, value):
    comm_port = "COM20"  # TODO: get comm_port?
    with serial.Serial(comm_port, baudrate=19200, timeout=1) as s:
        command_bytes = construct_command_packet(
            command_name, data_bytes_count=2, data=value
        )
        s.write(command_bytes)
        response = s.readline()
        return parse_response(command_name, response)


def read(command_name):
    comm_port = "COM20"  # TODO: get comm_port?
    with serial.Serial(comm_port, baudrate=19200, timeout=1) as s:
        command_bytes = construct_command_packet(
            command_name, data_bytes_count=0, data=None
        )
        s.write(command_bytes)
        response = s.readline()
        return parse_response(command_name, response)


def read_status():
    # command_hex = 0x09
    pass


def turn_on_off(on=True):
    # command_hex = 0x81
    # Command format: CA 00 01 81 08 (d1)...(d8)(cs)
    # Response format: CA 00 01 81 08 (d1)...(d8)(cs)
    # Data bytes meaning:
    #     (di: 0 = off, 1 = on, 2 = no change)
    #     d1 = unit on/off
    #     d2 = sensor enable
    #     d3 = faults enabled
    #     d4 = mute
    #     d5 = auto restart
    #     d6 = 0.01°C enable
    #     d7 = full range cool enable
    #     d8 = serial comm enable

    # Just turn on, change nothing else:
    # CA 00 01 81 08 01 02 02 02 02 02 02 02 66
    pass
