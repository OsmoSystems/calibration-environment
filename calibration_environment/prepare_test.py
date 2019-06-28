from typing import List
from unittest.mock import sentinel

import pytest

from . import prepare as module


class TestParseArgs(object):
    def test_all_args_parsed_appropriately(self):
        args_in: List[str] = [
            "--sequence",
            "experiment.csv",
            "--o2fraction",
            "21",
            "--loop",
            "--dry-run",
            "--gas-mixer-port",
            "COM1",
            "--water-bath-port",
            "COM2",
            "--read-count",
            "4",
            "--wait-time",
            "300",
        ]

        expected_args_out = {
            "sequence_csv": "experiment.csv",
            "o2_source_gas_fraction": 21,
            "loop": True,
            "dry_run": True,
            "gas_mixer_com_port": "COM1",
            "water_bath_com_port": "COM2",
            "read_count": 4,
            "collection_wait_time": 300,
        }

        assert module._parse_args(args_in) == expected_args_out

    def test_missing_required_args_throws(self):
        args_in: List[str] = []
        with pytest.raises(SystemExit):
            module._parse_args(args_in)


class TestGetCalibrationConfiguration(object):
    def test_all_configuration_options_returned(self, mocker):
        mocker.patch.object(
            module, "_open_sequence_file"
        ).return_value = sentinel.setpoints
        mocker.patch.object(
            module, "_get_output_filename"
        ).return_value = sentinel.filepath

        args_in: List[str] = [
            "--sequence",
            "experiment.csv",
            "--o2fraction",
            "21",
            "--loop",
            "--read-count",
            "5",
            "--wait-time",
            "300",
        ]

        expected_configuration = module.CalibrationConfiguration(
            sequence_csv="experiment.csv",
            setpoints=sentinel.setpoints,
            com_port_args={"gas_mixer": "COM19", "water_bath": "COM20"},
            o2_source_gas_fraction=21,
            loop=True,
            dry_run=False,
            output_csv=sentinel.filepath,
            read_count=5,
            collection_wait_time=300,
        )

        actual_configuratin = module.get_calibration_configuration(args_in)

        assert expected_configuration == actual_configuratin
