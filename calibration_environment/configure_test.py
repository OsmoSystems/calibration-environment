from datetime import datetime
from typing import List
from unittest.mock import sentinel

import pytest

from . import configure as module


class TestParseArgs(object):
    def test_all_args_parsed_appropriately(self):
        args_in = [
            "--setpoint-sequence-filepath",
            "experiment.csv",
            "--o2-source-fraction",
            ".21",
            "--loop",
            "--gas-mixer-port",
            "COM1",
            "--water-bath-port",
            "COM2",
            "--collection-interval",
            "50",
        ]

        expected_args_out = {
            "setpoint_sequence_csv_filepath": "experiment.csv",
            "o2_source_gas_fraction": 0.21,
            "loop": True,
            "gas_mixer_com_port": "COM1",
            "water_bath_com_port": "COM2",
            "collection_interval": 50,
        }

        assert module._parse_args(args_in) == expected_args_out

    def test_shorthand_args_parsed_appropriately(self):
        args_in = ["-s", "experiment.csv", "-o2", ".21"]

        expected_args_out = {
            "setpoint_sequence_csv_filepath": "experiment.csv",
            "o2_source_gas_fraction": 0.21,
            "loop": False,
            "gas_mixer_com_port": "COM22",
            "water_bath_com_port": "COM21",
            "collection_interval": 60,
        }

        assert module._parse_args(args_in) == expected_args_out

    def test_missing_required_args_throws(self):
        args_in: List[str] = []
        with pytest.raises(SystemExit):
            module._parse_args(args_in)

    def test_unrecognized_args_throws(self):
        args_in = ["--extra"]
        with pytest.raises(SystemExit):
            module._parse_args(args_in)


class TestGetCalibrationConfiguration(object):
    def test_returns_all_configuration_options(self, mocker):
        mocker.patch.object(
            module, "_read_setpoint_sequence_file"
        ).return_value = sentinel.setpoints
        mocker.patch.object(
            module, "_get_output_filename"
        ).return_value = sentinel.filepath

        start_date = datetime.now()

        args_in = ["-s", "experiment.csv", "-o2", ".21", "--loop"]

        expected_configuration = module.CalibrationConfiguration(
            setpoint_sequence_csv_filepath="experiment.csv",
            setpoints=sentinel.setpoints,
            com_ports={"gas_mixer": "COM22", "water_bath": "COM21"},
            o2_source_gas_fraction=0.21,
            loop=True,
            output_csv_filepath=sentinel.filepath,
            collection_interval=60,
        )

        actual_configuration = module.get_calibration_configuration(args_in, start_date)

        assert expected_configuration == actual_configuration
