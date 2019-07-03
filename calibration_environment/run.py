import sys
import logging
import time
from datetime import datetime, timedelta

import pandas as pd

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

    return pd.concat([gas_mixer_status, gas_ids, water_bath_status])


def collect_data_to_csv(
    setpoint,
    calibration_configuration,
    sequence_iteration_count=0,
    write_headers_to_file=True,
):
    """
        Read data from calibration environment sensors and write one row to
        output csv along with configuration data, optionally writing column headers.

        Args:
            gas_mixer: A gas_mixer driver module or stub
            water_bath: A water_bath driver module or stub
            setpoint: A setpoint DataFrame row
            calibration_configuration: A CalibrationConfiguration object
            equilibration_state: The current equilibration state of the system
            sequence_iteration_count: The current iteration of looping over the setpoint sequence file. Int.
            write_headers_to_file: Whether or not to write csv headers to output file.
    """

    # Read from each sensor and add to the DataFrame
    sensor_data = get_all_sensor_data(calibration_configuration.com_ports)

    row = pd.Series(
        {
            "iteration": sequence_iteration_count,
            "setpoint temperature": setpoint["temperature"],
            "setpoint flow rate": setpoint["flow_rate_slpm"],
            "setpoint target gas fraction": setpoint["o2_target_gas_fraction"],
            "o2 source gas fraction": calibration_configuration.o2_source_gas_fraction,
            "timestamp": datetime.now(),
            **dict(sensor_data),
        }
    )

    # Use mode="a" to append the row to the file
    pd.DataFrame(row).T.to_csv(
        calibration_configuration.output_csv_filepath,
        index=False,
        header=write_headers_to_file,
        mode="a",
    )


def run(cli_args=None):

    if cli_args is None:
        # First argument is the name of the command itself, not an "argument" we want to parse
        cli_args = sys.argv[1:]
    # Parse the configuration parameters from cli args
    calibration_configuration = get_calibration_configuration(cli_args)

    logging.info(
        f"Logging sensor data to {calibration_configuration.output_csv_filepath}"
    )

    water_bath_com_port = calibration_configuration.com_ports["water_bath"]
    gas_mixer_com_port = calibration_configuration.com_ports["gas_mixer"]

    water_bath.initialize(water_bath_com_port)

    sequence_iteration_count = 0
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
            # TODO: Equilibration Procedure Software Implementation
            # https://app.asana.com/0/1123279738062524/1128578386488633
            gas_mixer.start_constant_flow_mix(
                gas_mixer_com_port,
                setpoint["flow_rate_slpm"],
                setpoint["o2_target_gas_fraction"],
                calibration_configuration.o2_source_gas_fraction,
            )
            wait_for_gas_mixer_equilibration(gas_mixer_com_port)

            setpoint_equilibration_end_time = datetime.now() + timedelta(
                seconds=calibration_configuration.setpoint_wait_time
            )
            next_data_collection_time = datetime.now()

            while datetime.now() < setpoint_equilibration_end_time:
                # Wait before collecting next datapoint
                if datetime.now() < next_data_collection_time:
                    time.sleep(0.1)  # No need to totally peg the CPU
                    continue

                collect_data_to_csv(
                    setpoint,
                    calibration_configuration,
                    sequence_iteration_count=sequence_iteration_count,
                    write_headers_to_file=write_headers_to_file,
                )
                write_headers_to_file = False
                next_data_collection_time = datetime.now() + timedelta(
                    seconds=calibration_configuration.collection_interval
                )

        # Increment so we know which iteration we're on in the logs
        sequence_iteration_count += 1

        if not calibration_configuration.loop:
            break

    gas_mixer.stop_flow(gas_mixer_com_port)
    # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
    # water_bath.shutdown(water_bath_com_port)
