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
        ]

        expected_args_out = {
            "setpoint_sequence_csv_filepath": "experiment.csv",
            "o2_source_gas_fraction": 0.21,
            "loop": True,
            "gas_mixer_com_port": "COM1",
            "water_bath_com_port": "COM2",
            "ysi_com_port": "COM3",
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
            "ysi_com_port": "COM11",
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


class TestGetCalibrationConfiguration:
    def test_returns_all_configuration_options(self, mocker):
        mocker.patch.object(
            module, "_read_setpoint_sequence_file", return_value=sentinel.setpoints
        )
        mocker.patch.object(
            module, "_get_output_filename", return_value=sentinel.filepath
        )
        mocker.patch.object(module, "validate_setpoints", return_value=pd.DataFrame())

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
        )

        actual_configuration = module.get_calibration_configuration(args_in, start_date)

        assert expected_configuration == actual_configuration

    def test_raises_on_invalid_setpoints(self, mocker):
        test_setpoints = pd.DataFrame(
            [
                {
                    "temperature": 101,
                    "flow_rate_slpm": 2.5,
                    "o2_target_gas_fraction": 0.21,
                }
            ]
        )
        mocker.patch.object(
            module, "_read_setpoint_sequence_file", return_value=test_setpoints
        )
        mocker.patch.object(
            module, "_get_output_filename", return_value=sentinel.filepath
        )

        start_date = datetime.now()

        args_in = ["-s", "experiment.csv", "-o2", ".21", "--loop"]

        with pytest.raises(ValueError, match="Invalid setpoints detected"):
            module.get_calibration_configuration(args_in, start_date)


class TestValidateSetpoints:
    @pytest.mark.parametrize(
        "temperature, flow_rate_slpm, o2_target_gas_fraction, o2_source_gas_fraction, expected_errors",
        [
            (15, 2.5, 0.21, 0.21, []),
            (15, 5, 0, 0.1, []),
            (15, 5, 0.5, 1, []),
            (-1, 2.5, 0.21, 0.21, ["temperature too low"]),
            (101, 2.5, 0.21, 0.21, ["temperature too high"]),
            (15, 2.5, 0.42, 0.21, ["target gas O2 fraction too high"]),
            (15, 5, 0.21, 0.21, ["O2 flow rate too high"]),
            (15, 15, 0.21, 0.7, ["O2 flow rate too high", "N2 flow rate too high"]),
            (15, 15, 0.0, 0.21, ["N2 flow rate too high"]),
            (15, 2.5, 0.001, 0.21, ["O2 flow rate too low"]),
            (15, 2.5, 0.209, 0.21, ["N2 flow rate too low"]),
        ],
    )
    def test_returns_invalid_setpoints(
        self,
        temperature,
        flow_rate_slpm,
        o2_target_gas_fraction,
        o2_source_gas_fraction,
        expected_errors,
    ):
        setpoints = pd.DataFrame(
            [
                {
                    "temperature": temperature,
                    "flow_rate_slpm": flow_rate_slpm,
                    "o2_target_gas_fraction": o2_target_gas_fraction,
                }
            ]
        )

        invalid_setpoints = module.validate_setpoints(setpoints, o2_source_gas_fraction)

        has_validation_errors = len(invalid_setpoints) > 0
        expects_validation_errors = len(expected_errors) > 0

        expected_error_columns = invalid_setpoints[expected_errors]

        assert has_validation_errors == expects_validation_errors
        assert expected_error_columns.all().all()
