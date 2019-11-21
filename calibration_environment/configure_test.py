from datetime import datetime
from typing import List
from unittest.mock import sentinel

import pytest
import pandas as pd

from . import configure as module


class TestParseArgs:
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
            "--ysi-port",
            "COM3",
            "--collection-interval",
            "50",
            "--cosmobot-hostname",
            "cosmohostname1",
            "-c",
            "cosmohostname2",
            "--cosmobot-experiment-name",
            "experiment1",
            "--cosmobot-interval",
            "4.9",
            "--cosmobot-exposure-time",
            "0.5",
            "--cosmobot-camera-warm-up",
            "2.5",
        ]

        expected_args_out = {
            "setpoint_sequence_csv_filepath": "experiment.csv",
            "o2_source_gas_fraction": 0.21,
            "loop": True,
            "gas_mixer_com_port": "COM1",
            "water_bath_com_port": "COM2",
            "ysi_com_port": "COM3",
            "collection_interval": 50,
            "cosmobot_experiment_name": "experiment1",
            "cosmobot_hostnames": ["cosmohostname1", "cosmohostname2"],
            "cosmobot_interval": 4.9,
            "cosmobot_exposure_time": 0.5,
            "cosmobot_camera_warm_up": 2.5,
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
            "ysi_com_port": "COM11",
            "collection_interval": 60,
            "cosmobot_hostnames": None,
            "cosmobot_experiment_name": None,
            "cosmobot_interval": None,
            "cosmobot_exposure_time": None,
            "cosmobot_camera_warm_up": None,
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

    @pytest.mark.parametrize(
        "cosmobot_args",
        (
            ["--cosmobot-experiment-name", "experiment_name"],
            ["--cosmobot-hostname", "hostname"],
            ["--cosmobot-interval", "123"],
            [
                "--cosmobot-experiment-name",
                "experiment_name",
                "--cosmobot-hostname",
                "hostname",
            ],
        ),
    )
    def test_raises_on_missing_cosmobot_args(self, cosmobot_args):
        minimal_args_in = [
            "-s",
            "experiment.csv",
            "-o2",
            ".21",
        ]
        args_in = minimal_args_in + cosmobot_args

        with pytest.raises(SystemExit):
            module._parse_args(args_in)


class TestGetCalibrationConfiguration:
    def test_returns_all_configuration_options(self, mocker):
        mocker.patch.object(
            module, "read_setpoint_sequence_file", return_value=sentinel.setpoints
        )
        mocker.patch.object(
            module, "_get_output_csv_filename", return_value=sentinel.filepath
        )
        mocker.patch.object(
            module, "get_validation_errors", return_value=pd.DataFrame()
        )

        start_date = datetime.now()

        args_in = ["-s", "experiment.csv", "-o2", ".21", "--loop"]

        expected_configuration = module.CalibrationConfiguration(
            setpoint_sequence_csv_filepath="experiment.csv",
            setpoints=sentinel.setpoints,
            com_ports={"gas_mixer": "COM22", "water_bath": "COM21", "ysi": "COM11"},
            o2_source_gas_fraction=0.21,
            loop=True,
            output_csv_filepath=sentinel.filepath,
            collection_interval=60,
            cosmobot_experiment_name=None,
            cosmobot_hostnames=None,
            cosmobot_interval=None,
            cosmobot_exposure_time=None,
            cosmobot_camera_warm_up=None,
            capture_images=False,
        )

        actual_configuration = module.get_calibration_configuration(args_in, start_date)

        assert expected_configuration == actual_configuration

    def test_does_not_raise_on_valid_setpoints(self, mocker):
        valid_setpoint = pd.DataFrame(
            [{"temperature": 15, "flow_rate_slpm": 2.5, "o2_fraction": 0.21}]
        )
        mocker.patch.object(
            module, "read_setpoint_sequence_file", return_value=valid_setpoint
        )
        mocker.patch.object(
            module, "_get_output_csv_filename", return_value=sentinel.filepath
        )

        start_date = datetime.now()

        args_in = ["-s", "experiment.csv", "-o2", ".21", "--loop"]

        module.get_calibration_configuration(args_in, start_date)

    def test_raises_on_invalid_setpoints(self, mocker):
        invalid_setpoint = pd.DataFrame(
            [
                {
                    "temperature": 101,  # Causes "temperature too high" error
                    "flow_rate_slpm": 2.5,
                    "o2_fraction": 0.21,
                }
            ]
        )
        mocker.patch.object(
            module, "read_setpoint_sequence_file", return_value=invalid_setpoint
        )
        mocker.patch.object(
            module, "_get_output_csv_filename", return_value=sentinel.filepath
        )

        start_date = datetime.now()

        args_in = ["-s", "experiment.csv", "-o2", ".21", "--loop"]

        with pytest.raises(ValueError, match="Invalid setpoints detected"):
            module.get_calibration_configuration(args_in, start_date)
