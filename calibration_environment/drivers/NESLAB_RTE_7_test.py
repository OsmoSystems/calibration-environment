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
        assert module.calculate_checksum(message_bytes) == expected_checksum


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
        actual_value = module.parse_data_bytes_as_float(data_bytes)
        assert actual_value == expected_value


class TestResponsePacket:
    def test_init(self):
        packet = module.ResponsePacket(b"\xCA\x00\x01\x20\x03\x11\x02\x71\x57")
        assert packet.prefix == 0xCA
        assert packet.device_address_msb == 0x00
        assert packet.device_address_lsb == 0x01
        assert packet.data_bytes_count == 0x03
        assert packet.data_bytes == b"\x11\x02\x71"
        assert packet.checksum == 0x57

    def test_sets_data_bytes_to_empty(self):
        packet = module.ResponsePacket(b"\xCA\x00\x01\x20\x00\xDE")
        assert packet.prefix == 0xCA
        assert packet.device_address_msb == 0x00
        assert packet.device_address_lsb == 0x01
        assert packet.data_bytes_count == 0x00
        assert packet.data_bytes == b""
        assert packet.checksum == 0xDE

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
    def test_validate_raises(self, name, response_bytes):
        with pytest.raises(ValueError):
            packet = module.ResponsePacket(response_bytes)
            packet.validate()
