import sys
import logging
import time
from datetime import datetime, timedelta

import pandas as pd

from .data_logging import collect_data_to_csv
from .drivers import gas_mixer
from .drivers import water_bath
from .equilibrate import (
    wait_for_temperature_equilibration,
    wait_for_gas_mixer_equilibration,
)
from .configure import get_calibration_configuration

logging_format = "%(asctime)s [%(levelname)s]--- %(message)s"
logging.basicConfig(
    level=logging.INFO, format=logging_format, handlers=[logging.StreamHandler()]
)


def _shut_down(gas_mixer_com_port, water_bath_com_port):
    """Turn off gas mixer and water bath"""
    try:
        gas_mixer.stop_flow_with_retry(gas_mixer_com_port)
    finally:
        # Ensure that the water bath gets turned off even if the gas mixer errors
        water_bath.send_settings_command_and_parse_response(
            water_bath_com_port, unit_on_off=False
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

    try:
        water_bath.initialize(water_bath_com_port)

        loop_count = 0

        while True:

            for _, setpoint in calibration_configuration.setpoints.iterrows():

                logging.info(f"Setting setpoint: {setpoint.to_dict()}")
                water_bath.send_command_and_parse_response(
                    water_bath_com_port,
                    command_name="Set Setpoint",
                    data=setpoint["temperature"],
                )
                wait_for_temperature_equilibration(
                    calibration_configuration, setpoint, loop_count
                )

                # Set the gas mixer ratio
                gas_mixer.start_constant_flow_mix_with_retry(
                    gas_mixer_com_port,
                    setpoint["flow_rate_slpm"],
                    setpoint["o2_fraction"],
                    calibration_configuration.o2_source_gas_fraction,
                )
                wait_for_gas_mixer_equilibration(
                    calibration_configuration, setpoint, loop_count
                )

                # use pd.Timedelta here for type safety (handles numpy ints)
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
                        setpoint, calibration_configuration, loop_count=loop_count
                    )

            # Increment so we know which iteration we're on in the logs
            loop_count += 1

            if not calibration_configuration.loop:
                break

    finally:
        # Ensure that the gas mixer and the water bath get turned off even if something
        # unexpected happens.
        _shut_down(gas_mixer_com_port, water_bath_com_port)
