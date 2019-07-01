from typing import List
from unittest.mock import sentinel

import pytest

from . import prepare as module


class TestParseArgs(object):
    def test_all_args_parsed_appropriately(self):
        args_in = [
            "--sequence",
            "experiment.csv",
            "--o2fraction",
            ".21",
            "--loop",
            "--dry-run",
            "--gas-mixer-port",
            "COM1",
            "--water-bath-port",
            "COM2",
            "--collection-interval",
            "50",
            "--wait-time",
            "300",
        ]

        expected_args_out = {
            "sequence_csv": "experiment.csv",
            "o2_source_gas_fraction": 0.21,
            "loop": True,
            "dry_run": True,
            "gas_mixer_com_port": "COM1",
            "water_bath_com_port": "COM2",
            "collection_interval": 50,
            "setpoint_wait_time": 300,
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
    def test_all_configuration_options_returned(self, mocker):
        mocker.patch.object(
            module, "_open_setpoint_sequence_file"
        ).return_value = sentinel.setpoints
        mocker.patch.object(
            module, "_get_output_filename"
        ).return_value = sentinel.filepath

        args_in = [
            "--sequence",
            "experiment.csv",
            "--o2fraction",
            ".21",
            "--loop",
            "--wait-time",
            "300",
        ]

        expected_configuration = module.CalibrationConfiguration(
            sequence_csv="experiment.csv",
            setpoints=sentinel.setpoints,
            com_port_args={"gas_mixer": "COM22", "water_bath": "COM21"},
            o2_source_gas_fraction=0.21,
            loop=True,
            dry_run=False,
            output_csv=sentinel.filepath,
            collection_interval=60,
            setpoint_wait_time=300,
        )

        actual_configuration = module.get_calibration_configuration(args_in)

        assert expected_configuration == actual_configuration