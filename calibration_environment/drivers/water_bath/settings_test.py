import pytest

from calibration_environment.drivers.water_bath import settings as module


PREFIX_AND_ADDR_DEFAULTS = dict(
    prefix=0xCA, device_address_msb=0x00, device_address_lsb=0x01
)


class TestConstructSettingsCommandPacket:
    def test_construct_settings_command_packet(self):
        settings = module.OnOffArraySettings(
            # Three Trues, three Falses and two Nones
            unit_on_off=True,
            external_sensor_enable=True,
            faults_enabled=True,
            mute=False,
            auto_restart=False,
            high_precision_enable=False,
            full_range_cool_enable=None,
            serial_comm_enable=None,
        )
        actual_packet = module._construct_settings_command_packet(settings)
        expected_packet = module.SerialPacket(
            command=0x81,
            data_bytes_count=0x08,
            data_bytes=b"\x01\x01\x01\x00\x00\x00\x02\x02",
            **PREFIX_AND_ADDR_DEFAULTS,
        )

        assert actual_packet == expected_packet


class TestParseSettingsDataBytes:
    def test_parse_settings_data_bytes(self):
        actual = module._parse_settings_data_bytes(b"\x01\x01\x02\x02\x02\x00\x02\x01")
        expected = module.OnOffArraySettings(1, 1, 2, 2, 2, 0, 2, 1)

        assert actual == expected


class TestValidateSettings:
    default_initialization_settings = module.OnOffArraySettings(
        unit_on_off=True,
        external_sensor_enable=False,
        faults_enabled=None,
        mute=None,
        auto_restart=None,
        high_precision_enable=True,
        full_range_cool_enable=None,
        serial_comm_enable=True,
    )

    def test_validate_initialization_settings_does_not_raise_if_correct(self):
        module._validate_initialized_settings(self.default_initialization_settings)

    @pytest.mark.parametrize(
        "setting, incorrect_value",
        [
            ("unit_on_off", False),
            ("external_sensor_enable", True),
            ("high_precision_enable", False),
            ("serial_comm_enable", False),
        ],
    )
    def test_validate_initialization_settings_raises(self, setting, incorrect_value):
        with pytest.raises(ValueError):
            settings_with_one_error = self.default_initialization_settings._asdict()
            settings_with_one_error[setting] = incorrect_value

            module._validate_initialized_settings(
                module.OnOffArraySettings(**settings_with_one_error)
            )

    def test_validate_initialization_settings_raises_on_multiple_errors(self):
        with pytest.raises(ValueError):
            settings_with_multiple_errors = (
                self.default_initialization_settings._asdict()
            )
            settings_with_multiple_errors["external_sensor_enable"] = False
            settings_with_multiple_errors["serial_comm_enable"] = False

            module._validate_initialized_settings(
                module.OnOffArraySettings(**settings_with_multiple_errors)
            )
