import argparse
from datetime import datetime
from collections import namedtuple

from typing import List, Dict

import pandas as pd

CalibrationConfiguration = namedtuple(
    "CalibrationConfiguration",
    [
        "sequence_csv",  # Filepath to setpoint sequence csv file
        "setpoints",
        "com_port_args",
        "o2_source_gas_fraction",
        "loop",
        "dry_run",
        "output_csv",
        "read_count",
        "collection_wait_time",
    ],
)


def _parse_args(args: List[str]) -> Dict:
    arg_parser = argparse.ArgumentParser(
        description=(""), formatter_class=argparse.RawTextHelpFormatter
    )

    arg_parser.add_argument(
        "--sequence",
        required=True,
        type=str,
        help="setpoint sequence csv filepath",
        dest="sequence_csv",
    )

    arg_parser.add_argument(
        "--o2fraction",
        dest="o2_source_gas_fraction",
        required=True,
        type=int,
        help="O2 percent connected to MFC2",
    )

    arg_parser.add_argument(
        "--loop",
        dest="loop",
        required=False,
        action="store_true",
        default=False,
        help="loop through the setpoint sequence until it is stopped manually",
    )

    arg_parser.add_argument(
        "--dry-run",
        dest="dry_run",
        required=False,
        action="store_true",
        default=False,
        help="disable using real sensors",
    )

    arg_parser.add_argument(
        "--gas-mixer-port",
        dest="gas_mixer_com_port",
        required=False,
        default="COM19",
        help="gas mixer COM port address",
    )

    arg_parser.add_argument(
        "--water-bath-port",
        dest="water_bath_com_port",
        required=False,
        default="COM20",
        help="water bath COM port address",
    )

    arg_parser.add_argument(
        "--read-count",
        dest="read_count",
        required=True,
        type=int,
        help="number of sensor readings to take at each setpoint",
    )

    arg_parser.add_argument(
        "--wait-time",
        dest="collection_wait_time",
        required=True,
        type=int,
        help="time in seconds to wait between reading sensors",
    )

    calibration_arg_namespace, _ = arg_parser.parse_known_args(args)
    return vars(calibration_arg_namespace)


def _open_sequence_file(sequence_csv_filepath):
    sequences = pd.read_csv(sequence_csv_filepath)

    return sequences


def _get_output_filename():
    start_date = datetime.now()

    return f"{start_date}_calibration.csv"


def get_calibration_configuration(cli_args):
    args = _parse_args(cli_args)

    com_port_args = {
        "gas_mixer": args["gas_mixer_com_port"],
        "water_bath": args["water_bath_com_port"],
    }

    calibration_configuration = CalibrationConfiguration(
        sequence_csv=args["sequence_csv"],
        setpoints=_open_sequence_file(args["sequence_csv"]),
        com_port_args=com_port_args,
        o2_source_gas_fraction=args["o2_source_gas_fraction"],
        loop=args["loop"],
        dry_run=args["dry_run"],
        output_csv=_get_output_filename(),
        read_count=args["read_count"],
        collection_wait_time=args["collection_wait_time"],
    )

    return calibration_configuration
