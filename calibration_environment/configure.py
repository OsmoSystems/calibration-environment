import argparse
from datetime import datetime
from collections import namedtuple

from typing import List, Dict

import pandas as pd

DEFAULT_GAS_MIXER_COM_PORT = "COM22"
DEFAULT_WATER_BATH_COM_PORT = "COM21"

CalibrationConfiguration = namedtuple(
    "CalibrationConfiguration",
    [
        "setpoint_sequence_csv_filepath",
        "setpoints",
        "com_ports",
        "o2_source_gas_fraction",
        "loop",
        "output_csv_filepath",
        "collection_interval",
    ],
)


def _parse_args(args: List[str]) -> Dict:
    arg_parser = argparse.ArgumentParser(
        description=(""), formatter_class=argparse.RawTextHelpFormatter
    )

    arg_parser.add_argument(
        "-s",
        "--setpoint-sequence-filepath",
        required=True,
        type=str,
        help="setpoint sequence csv filepath",
        dest="setpoint_sequence_csv_filepath",
    )

    arg_parser.add_argument(
        "-o2",
        "--o2-source-fraction",
        dest="o2_source_gas_fraction",
        required=True,
        type=float,
        help="O2 fraction connected to MFC2",
    )

    arg_parser.add_argument(
        "--loop",
        required=False,
        action="store_true",
        default=False,
        help="loop through the setpoint sequence until it is stopped manually",
    )

    arg_parser.add_argument(
        "--gas-mixer-port",
        dest="gas_mixer_com_port",
        required=False,
        default=DEFAULT_GAS_MIXER_COM_PORT,
        help=f"override gas mixer COM port address, defaults to {DEFAULT_GAS_MIXER_COM_PORT}",
    )

    arg_parser.add_argument(
        "--water-bath-port",
        dest="water_bath_com_port",
        required=False,
        default=DEFAULT_WATER_BATH_COM_PORT,
        help=f"overrider water bath COM port address, defaults to {DEFAULT_WATER_BATH_COM_PORT}",
    )

    arg_parser.add_argument(
        "--collection-interval",
        default=60,
        type=int,
        help="time in seconds to wait between reading sensors",
    )

    calibration_arg_namespace = arg_parser.parse_args(args)
    return vars(calibration_arg_namespace)


def _open_setpoint_sequence_file(sequence_csv_filepath):
    sequences = pd.read_csv(sequence_csv_filepath)

    return sequences


# Copy pasta from run experiment
def iso_datetime_for_filename(datetime_):
    """ Returns datetime as a ISO-ish format string that can be used in filenames (which can't inclue ":")
        datetime(2018, 1, 1, 12, 1, 1) --> '2018-01-01--12-01-01'
    """
    return datetime_.strftime("%Y-%m-%d--%H-%M-%S")


def _get_output_filename(start_date):
    return f"{iso_datetime_for_filename(start_date)}_calibration.csv"


def get_calibration_configuration(
    cli_args: List[str], start_date: datetime
) -> CalibrationConfiguration:
    args = _parse_args(cli_args)

    com_ports = {
        "gas_mixer": args["gas_mixer_com_port"],
        "water_bath": args["water_bath_com_port"],
    }

    calibration_configuration = CalibrationConfiguration(
        setpoint_sequence_csv_filepath=args["setpoint_sequence_csv_filepath"],
        setpoints=_open_setpoint_sequence_file(args["setpoint_sequence_csv_filepath"]),
        com_ports=com_ports,
        o2_source_gas_fraction=args["o2_source_gas_fraction"],
        loop=args["loop"],
        output_csv_filepath=_get_output_filename(start_date),
        collection_interval=args["collection_interval"],
    )

    return calibration_configuration
