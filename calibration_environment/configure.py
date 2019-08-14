import argparse
from datetime import datetime
from collections import namedtuple
import time

from typing import List, Dict

from .setpoints import read_setpoint_sequence_file, get_validation_errors

DEFAULT_GAS_MIXER_COM_PORT = "COM22"
DEFAULT_WATER_BATH_COM_PORT = "COM21"
DEFAULT_YSI_COM_PORT = "COM11"

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
        "cosmobot_hostname",
        "cosmobot_experiment_name",
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
        "-e",
        "--cosmobot-experiment-name",
        required=True,
        type=str,
        help="cosmobot experiment name for run_experiment",
    )

    arg_parser.add_argument(
        "--cosmobot-hostname",
        required=False,
        default="192.168.1.153",
        type=str,
        help="cosmobot hostname or ip address",
    )

    arg_parser.add_argument(
        "--loop",
        required=False,
        action="store_true",
        default=False,
        help=(
            "loop through the setpoint sequence until it is stopped manually. "
            "Default: run through setpoints exactly once"
        ),
    )

    arg_parser.add_argument(
        "--gas-mixer-port",
        dest="gas_mixer_com_port",
        required=False,
        default=DEFAULT_GAS_MIXER_COM_PORT,
        help=f"override gas mixer COM port address. Default: {DEFAULT_GAS_MIXER_COM_PORT}",
    )

    arg_parser.add_argument(
        "--water-bath-port",
        dest="water_bath_com_port",
        required=False,
        default=DEFAULT_WATER_BATH_COM_PORT,
        help=f"override water bath COM port address. Default: {DEFAULT_WATER_BATH_COM_PORT}",
    )

    arg_parser.add_argument(
        "--ysi-port",
        dest="ysi_com_port",
        required=False,
        default=DEFAULT_YSI_COM_PORT,
        help=f"override YSI COM port address. Default: {DEFAULT_YSI_COM_PORT}",
    )

    arg_parser.add_argument(
        "--collection-interval",
        default=60,
        type=int,
        help="time in seconds to wait between reading sensors",
    )

    calibration_arg_namespace = arg_parser.parse_args(args)
    return vars(calibration_arg_namespace)


# Copy pasta from run experiment
def iso_datetime_for_filename(datetime_):
    """ Returns datetime as a ISO-ish format string that can be used in filenames (which can't inclue ":")
        datetime(2018, 1, 1, 12, 1, 1) --> '2018-01-01--12-01-01'
    """
    return datetime_.strftime("%Y-%m-%d--%H-%M-%S")


def _get_output_csv_filename(start_date):
    return f"{iso_datetime_for_filename(start_date)}_calibration.csv"


def get_calibration_configuration(
    cli_args: List[str], start_date: datetime
) -> CalibrationConfiguration:
    args = _parse_args(cli_args)

    setpoints = read_setpoint_sequence_file(args["setpoint_sequence_csv_filepath"])

    setpoint_errors = get_validation_errors(setpoints, args["o2_source_gas_fraction"])
    if len(setpoint_errors):
        raise ValueError(f"Invalid setpoints detected:\n{setpoint_errors}")

    com_ports = {
        "gas_mixer": args["gas_mixer_com_port"],
        "water_bath": args["water_bath_com_port"],
        "ysi": args["ysi_com_port"],
    }

    # timestamp is added to make the name unique across calibration runs
    timestamp = time.time()
    cosmobot_experiment_name = f'{args["cosmobot_experiment_name"]}_{timestamp}'

    calibration_configuration = CalibrationConfiguration(
        setpoint_sequence_csv_filepath=args["setpoint_sequence_csv_filepath"],
        setpoints=setpoints,
        com_ports=com_ports,
        o2_source_gas_fraction=args["o2_source_gas_fraction"],
        loop=args["loop"],
        output_csv_filepath=_get_output_csv_filename(start_date),
        collection_interval=args["collection_interval"],
        cosmobot_experiment_name=cosmobot_experiment_name,
        cosmobot_hostname=args["cosmobot_hostname"],
    )

    return calibration_configuration
