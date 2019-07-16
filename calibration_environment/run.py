import sys
import logging
import time
from datetime import datetime, timedelta

import pandas as pd

from .drivers import gas_mixer
from .drivers import water_bath
from .drivers import ysi
from .equilibrate import (
    wait_for_temperature_equilibration,
    wait_for_gas_mixer_equilibration,
)
from .configure import get_calibration_configuration, CalibrationConfiguration

logging_format = "%(asctime)s [%(levelname)s]--- %(message)s"
logging.basicConfig(
    level=logging.INFO, format=logging_format, handlers=[logging.StreamHandler()]
)


def get_all_sensor_data(com_ports):
    gas_mixer_status = gas_mixer.get_mixer_status(com_ports["gas_mixer"]).add_prefix(
        "gas mixer "
    )

    gas_ids = gas_mixer.get_gas_ids(com_ports["gas_mixer"]).add_suffix(" gas ID")

    water_bath_status = pd.Series(
        {
            "internal temperature (C)": water_bath.send_command_and_parse_response(
                com_ports["water_bath"], "Read Internal Temperature"
            ),
            "external sensor temperature (C)": water_bath.send_command_and_parse_response(
                com_ports["water_bath"], "Read External Sensor"
            ),
        }
    ).add_prefix("water bath ")

    ysi_status = ysi.get_standard_sensor_values(com_ports["ysi"]).add_prefix("YSI ")

    return pd.concat([gas_mixer_status, gas_ids, water_bath_status, ysi_status])


def collect_data_to_csv(
    setpoint: pd.Series,
    calibration_configuration: CalibrationConfiguration,
    loop_count: int = 0,
    write_headers_to_file: bool = True,
):
    """
        Read data from calibration environment sensors and write one row to
        output csv along with configuration data, optionally writing column headers.

        Args:
            setpoint: A setpoint DataFrame row
            calibration_configuration: A CalibrationConfiguration object
            loop_count: The current iteration of looping over the setpoint sequence file.
            write_headers_to_file: Whether or not to write csv headers to output file.
    """

    # Read from each sensor and add to the DataFrame
    sensor_data = get_all_sensor_data(calibration_configuration.com_ports)

    row = pd.DataFrame(
        [
            {
                "loop count": loop_count,
                "setpoint temperature (C)": setpoint["temperature"],
                "setpoint hold time seconds": setpoint["hold_time"],
                "setpoint flow rate (SLPM)": setpoint["flow_rate_slpm"],
                "setpoint target gas fraction": setpoint["o2_target_gas_fraction"],
                "o2 source gas fraction": calibration_configuration.o2_source_gas_fraction,
                "timestamp": datetime.now(),
                **dict(sensor_data),
            }
        ]
    ).sort_index(
        axis=1
    )  # Sort the index so columns are always in the same order

    # Use mode="a" to append the row to the file
    row.to_csv(
        calibration_configuration.output_csv_filepath,
        index=False,
        header=write_headers_to_file,
        mode="a",
    )


def run(cli_args=None):
    start_date = datetime.now()

    if cli_args is None:
        # First argument is the name of the command itself, not an "argument" we want to parse
        cli_args = sys.argv[1:]
    # Parse the configuration parameters from cli args
    calibration_configuration = get_calibration_configuration(cli_args, start_date)

    logging.info(
        f"Logging sensor data to {calibration_configuration.output_csv_filepath}"
    )

    water_bath_com_port = calibration_configuration.com_ports["water_bath"]
    gas_mixer_com_port = calibration_configuration.com_ports["gas_mixer"]

    water_bath.initialize(water_bath_com_port)

    loop_count = 0
    write_headers_to_file = True

    while True:

        for _, setpoint in calibration_configuration.setpoints.iterrows():

            water_bath.send_command_and_parse_response(
                water_bath_com_port,
                command_name="Set Setpoint",
                data=setpoint["temperature"],
            )
            wait_for_temperature_equilibration(water_bath_com_port)

            # Set the gas mixer ratio
            gas_mixer.start_constant_flow_mix(
                gas_mixer_com_port,
                setpoint["flow_rate_slpm"],
                setpoint["o2_target_gas_fraction"],
                calibration_configuration.o2_source_gas_fraction,
            )
            wait_for_gas_mixer_equilibration(gas_mixer_com_port)

            # use pd.Timedelta here for type safety
            setpoint_hold_end_time = datetime.now() + pd.Timedelta(
                seconds=setpoint["hold_time"]
            )
            next_data_collection_time = datetime.now()

            while datetime.now() < setpoint_hold_end_time:
                # Wait before collecting next datapoint
                if datetime.now() < next_data_collection_time:
                    time.sleep(0.1)  # No need to totally peg the CPU
                    continue

                next_data_collection_time = next_data_collection_time + timedelta(
                    seconds=calibration_configuration.collection_interval
                )

                collect_data_to_csv(
                    setpoint,
                    calibration_configuration,
                    loop_count=loop_count,
                    write_headers_to_file=write_headers_to_file,
                )
                write_headers_to_file = False

        # Increment so we know which iteration we're on in the logs
        loop_count += 1

        if not calibration_configuration.loop:
            break

    gas_mixer.stop_flow(gas_mixer_com_port)
    water_bath.send_settings_command_and_parse_response(
        water_bath_com_port, unit_on_off=False
    )
