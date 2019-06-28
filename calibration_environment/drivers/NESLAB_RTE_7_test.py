from binascii import hexlify
import pytest

from . import NESLAB_RTE_7 as module


class TestCalculateChecksum:
    @pytest.mark.parametrize(
        "message_bytes, expected_checksum",
        [
            # Examples from the datasheet
            (b"\x00\x01\x00\x00", 0xFE),
            (b"\x00\x01\x09\x00", 0xF5),
            (b"\x00\x01\x20\x03\x11\x02\x71", 0x57),
            (b"\x00\x03\xF0\x02\x01\x2C", 0xDD),
            (b"\x00\x03\xF0\x03\x11\x01\x2C", 0xCB),
            # Other examples
            (b"\x00\x01\x81\x08\x01\x02\x02\x02\x02\x02\x02\x02", 0x66),
        ],
    )
    def test_calculate_checksum(self, message_bytes, expected_checksum):
        assert module._calculate_checksum(message_bytes) == expected_checksum


class TestParseDataBytesAsFloat:
    @pytest.mark.parametrize(
        "data_bytes, expected_value",
        [
            # Examples from the datasheet
            (b"\x11\x02\x71", 62.5),  # Units: degrees C
            (b"\x11\x01\x2C", 30.0),  # Units: degrees C
            (b"\x10\x02\x71", 62.5),
            (b"\x10\x01\x2C", 30.0),
            # Other examples
            (b"\x21\x02\x71", 6.25),  # Units: degrees C
            (b"\x21\x01\x2C", 3.00),  # Units: degrees C
            (b"\x20\x02\x71", 6.25),
            (b"\x20\x01\x2C", 3.00),
        ],
    )
    def test_parse_data_bytes_as_float(self, data_bytes, expected_value):
        actual_value = module._parse_data_bytes_as_float(data_bytes)
        assert actual_value == expected_value


class TestSerialPacket:
    @pytest.mark.parametrize(
        "name, packet_bytes, expected_packet",
        [
            (
                "packet with data bytes",
                b"\xCA\x00\x01\x20\x03\x11\x02\x71\x57",
                module.SerialPacket(
                    prefix=0xCA,
                    device_address_msb=0x00,
                    device_address_lsb=0x01,
                    command=0x20,
                    data_bytes_count=0x03,
                    data_bytes=b"\x11\x02\x71",
                    checksum=0x57,
                ),
            ),
            (
                "packet with no data bytes",
                b"\xCA\x00\x01\x20\x00\xDE",
                module.SerialPacket(
                    prefix=0xCA,
                    device_address_msb=0x00,
                    device_address_lsb=0x01,
                    command=0x20,
                    data_bytes_count=0x00,
                    data_bytes=b"",
                    checksum=0xDE,
                ),
            ),
        ],
    )
    def test_init_from_bytes(self, name, packet_bytes, expected_packet):
        actual_packet = module.SerialPacket.from_bytes(packet_bytes)
        assert actual_packet == expected_packet

    @pytest.mark.parametrize(
        "name, response_bytes",
        [
            ("incorrect prefix", b"\xAA\x00\x01\x20\x04\x11\x02\x71\x57"),
            ("incorrect address msb", b"\xCA\x01\x01\x20\x04\x11\x02\x71\x57"),
            ("incorrect address lsb", b"\xCA\x00\x99\x20\x04\x11\x02\x71\x57"),
            ("data byte count mismatch", b"\xCA\x00\x01\x20\x04\x11\x02\x71\x57"),
            ("incorrect checksum", b"\xCA\x00\x01\x20\x03\x11\x02\x71\x58"),
        ],
    )
    def test_init_from_bytes_raises_if_invalid(self, name, response_bytes):
        with pytest.raises(ValueError):
            module.SerialPacket.from_bytes(response_bytes)

    @pytest.mark.parametrize(
        "name, command, data_bytes, expected_packet",
        [
            (
                "command with data bytes",
                0x20,
                b"\x11\x02\x71",
                module.SerialPacket(
                    prefix=0xCA,
                    device_address_msb=0x00,
                    device_address_lsb=0x01,
                    command=0x20,
                    data_bytes_count=0x03,
                    data_bytes=b"\x11\x02\x71",
                    checksum=0x57,
                ),
            ),
            (
                "command with no data bytes",
                0x20,
                b"",
                module.SerialPacket(
                    prefix=0xCA,
                    device_address_msb=0x00,
                    device_address_lsb=0x01,
                    command=0x20,
                    data_bytes_count=0x00,
                    data_bytes=b"",
                    checksum=0xDE,
                ),
            ),
        ],
    )
    def test_init_from_command(self, name, command, data_bytes, expected_packet):
        actual_packet = module.SerialPacket.from_command(command, data_bytes)
        assert actual_packet == expected_packet

    @pytest.mark.parametrize(
        "packet_bytes",
        [
            b"\xCA\x00\x01\x20\x03\x11\x02\x71\x57",
            b"\xCA\x00\x01\x20\x00\xDE",
            b"\xCA\x00\x01\x00\x00\xFE",
            b"\xCA\x00\x01\x09\x00\xF5",
            b"\xCA\x00\x01\x20\x03\x11\x02\x71\x57",
            b"\xCA\x00\x01\xF0\x02\x01\x2C\xDF",
            b"\xCA\x00\x01\xF0\x03\x11\x01\x2C\xCD",
        ],
    )
    def test_init_from_bytes_round_trip_to_bytes(self, packet_bytes):
        packet = module.SerialPacket.from_bytes(packet_bytes)
        # hexlify to make error message more readable
        assert hexlify(packet.to_bytes()) == hexlify(packet_bytes)


class TestConstructCommandPacket:
    @pytest.mark.parametrize(
        "command_name, data, expected_packet_bytes",
        [
            ("Read Internal Temperature", None, b"\xCA\x00\x01\x20\x00\xDE"),
            ("Read External Sensor", None, b"\xCA\x00\x01\x21\x00\xDD"),
            ("Read Setpoint", None, b"\xCA\x00\x01\x70\x00\x8E"),
            ("Read Low Temperature Limit", None, b"\xCA\x00\x01\x40\x00\xBE"),
            ("Read High Temperature Limit", None, b"\xCA\x00\x01\x60\x00\x9E"),
            ("Read Heat Proportional Band", None, b"\xCA\x00\x01\x71\x00\x8D"),
            ("Read Heat Integral", None, b"\xCA\x00\x01\x72\x00\x8C"),
            ("Read Heat Derivative", None, b"\xCA\x00\x01\x73\x00\x8B"),
            ("Read Cool Proportional Band", None, b"\xCA\x00\x01\x74\x00\x8A"),
            ("Read Cool Integral", None, b"\xCA\x00\x01\x75\x00\x89"),
            ("Read Cool Derivative", None, b"\xCA\x00\x01\x76\x00\x88"),
            ("Set Setpoint", 30.0, b"\xCA\x00\x01\xF0\x02\x01\x2C\xDF"),
            ("Set Setpoint", 62.5, b"\xCA\x00\x01\xF0\x02\x02\x71\x99"),
        ],
    )
    def test_construct_command(self, command_name, data, expected_packet_bytes):
        packet = module._construct_command_packet(command_name, data=data)
        # hexlify to make error message more readable
        assert hexlify(packet.to_bytes()) == hexlify(expected_packet_bytes)


class TestConstructSettingsCommandPacket:
    def test_construct_settings_command_packet(self):
        actual_packet = module._construct_settings_command_packet()
        expected_packet = module.SerialPacket(
            prefix=0xCA,
            device_address_msb=0x00,
            device_address_lsb=0x01,
            command=0x81,
            data_bytes_count=0x08,
            data_bytes=b"\x01\x01\x02\x02\x02\x00\x02\x01",
            checksum=0x6A,
        )
        assert actual_packet == expected_packet


class TestParseSettingsDataBytes:
    def test_parse_settings_data_bytes(self):
        actual = module._parse_settings_data_bytes(b"\x01\x01\x02\x02\x02\x00\x02\x01")
        expected = module.OnOffArraySettings(1, 1, 2, 2, 2, 0, 2, 1)

        assert actual == expected


class TestValidateSettings:
    def test_validate_settings_does_not_raise_if_valid(self):
        module._validate_settings(module.OnOffArraySettings(1, 1, 2, 2, 2, 0, 2, 1))

    def test_validate_settings_raises_on_single_error(self):
        with pytest.raises(ValueError):
            module._validate_settings(module.OnOffArraySettings(0, 1, 2, 2, 2, 0, 2, 1))

    def test_validate_settings_raises_on_multiple_errors(self):
        with pytest.raises(ValueError):
            module._validate_settings(module.OnOffArraySettings(0, 1, 2, 2, 2, 1, 2, 1))


class TestCheckForErrorResponse:
    def test_check_for_error_response_returns_none_on_normal_response(self):
        serial_packet = module.SerialPacket(
            prefix=0xCA,
            device_address_msb=0x00,
            device_address_lsb=0x01,
            command=0x20,
            data_bytes_count=0x00,
            data_bytes=b"",
            checksum=0xDE,
        )

        assert module._check_for_error_response(serial_packet) is None

    def test_check_for_error_response_identifies_bad_command_error_type(self):
        serial_packet = module.SerialPacket(
            prefix=0xCA,
            device_address_msb=0x00,
            device_address_lsb=0x01,
            command=0x0F,
            data_bytes_count=0x02,
            data_bytes=b"\x01\x99",
            checksum=0x53,
        )

        with pytest.raises(module.ErrorResponse) as e:
            module._check_for_error_response(serial_packet)

        print(e.value)
        assert "Bad Command" in str(e.value)

    def test_check_for_error_response_identifies_bad_checksum_error_type(self):
        serial_packet = module.SerialPacket(
            prefix=0xCA,
            device_address_msb=0x00,
            device_address_lsb=0x01,
            command=0x0F,
            data_bytes_count=0x02,
            data_bytes=b"\x03\x99",
            checksum=0x51,
        )

        with pytest.raises(module.ErrorResponse) as e:
            module._check_for_error_response(serial_packet)

        assert "Bad Checksum" in str(e.value)

    def test_check_for_error_response_identifies_echoed_command(self):
        serial_packet = module.SerialPacket(
            prefix=0xCA,
            device_address_msb=0x00,
            device_address_lsb=0x01,
            command=0x0F,
            data_bytes_count=0x02,
            data_bytes=b"\x03\x99",
            checksum=0x51,
        )

        with pytest.raises(module.ErrorResponse) as e:
            module._check_for_error_response(serial_packet)

        assert f"0x{0x99:02X}" in str(e.value)
