import sys
import logging
import time
from datetime import datetime, timedelta

import pandas as pd

from . import cosmobot
from .configure import get_calibration_configuration
from .data_logging import collect_data_to_csv
from .drivers import gas_mixer, water_bath
from .equilibrate import wait_for_temperature_equilibration, wait_for_do_equilibration
from .notifications import post_slack_message
from .status import check_status


def _shut_down(gas_mixer_com_port, water_bath_com_port):
    """Turn off gas mixer and water bath"""
    logging.info("Shutting down gas mixer and temperature controlled water bath.")
    try:
        logging.info("Shutting down gas mixer...")
        gas_mixer.stop_flow_with_retry(gas_mixer_com_port)
        logging.info("Gas mixer flow stopped.")
    finally:
        # Ensure that the water bath gets turned off even if the gas mixer errors

        # If the water bath was _just_ turned on immediately before this, turning it off doesn't work unless we wait
        # a few seconds.
        logging.info("Giving the water bath 5 seconds before we shut it off...")
        time.sleep(5)
        logging.info("Shutting down water bath.")
        water_bath.send_settings_command_and_parse_response(
            water_bath_com_port, unit_on_off=False
        )
        logging.info("Water bath shut down.")


def run(cli_args=None):
    logging_format = "%(asctime)s [%(levelname)s]--- %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=logging_format, handlers=[logging.StreamHandler()]
    )

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

    if calibration_configuration.capture_images:
        cosmobot_ssh_client = cosmobot.get_ssh_client(
            calibration_configuration.cosmobot_hostname
        )

    try:
        water_bath.initialize(water_bath_com_port)

        loop_count = 0

        while True:

            for i, setpoint in calibration_configuration.setpoints.iterrows():
                last_setpoint = (
                    calibration_configuration.setpoints.iloc[i - 1] if i > 0 else None
                )

                logging.info(f"Setting setpoint: {setpoint.to_dict()}")
                water_bath.send_command_and_parse_response(
                    water_bath_com_port,
                    command_name="Set Setpoint",
                    data=setpoint["temperature"],
                )

                # only wait for temperature equilibration if temperature
                # changed from last setpoint
                if (
                    last_setpoint is None
                    or last_setpoint["temperature"] != setpoint["temperature"]
                ):
                    # Stop gas mixer while we wait for temperature equilibration to conserve gas
                    gas_mixer.stop_flow_with_retry(gas_mixer_com_port)
                    wait_for_temperature_equilibration(
                        calibration_configuration, setpoint, loop_count
                    )

                    # Resume gas flow and ensure temperature remains equilibrated
                    gas_mixer.start_constant_flow_mix_with_retry(
                        gas_mixer_com_port,
                        setpoint["flow_rate_slpm"],
                        setpoint["o2_fraction"],
                        calibration_configuration.o2_source_gas_fraction,
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
                wait_for_do_equilibration(
                    calibration_configuration, setpoint, loop_count
                )

                # use pd.Timedelta here for type safety (handles numpy ints)
                setpoint_hold_end_time = datetime.now() + pd.Timedelta(
                    seconds=setpoint["hold_time"]
                )
                next_data_collection_time = datetime.now()

                if calibration_configuration.capture_images:
                    # start cosmobot image capture
                    run_experiment_streams = cosmobot.run_experiment(
                        cosmobot_ssh_client,
                        calibration_configuration.cosmobot_experiment_name,
                        setpoint["hold_time"],
                        calibration_configuration.cosmobot_exposure_time,
                    )

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
                    check_status(calibration_configuration.com_ports)

                if calibration_configuration.capture_images:
                    # wait for run_experiment to complete (raises if it has a bad exit code)
                    logging.info(
                        "Waiting for run_experiment on cosmobot to complete..."
                    )
                    cosmobot.wait_for_exit(run_experiment_streams)
                    logging.info("Cosmobot run_experiment process completed")

            # Increment so we know which iteration we're on in the logs
            loop_count += 1

            if not calibration_configuration.loop:
                break

    # Catch interrupts and unexpected errors so we can notify on slack.
    # Re-raise so that we still get the stack traces
    except KeyboardInterrupt as e:
        logging.warning("Keyboard interrupt! Shutting down... (please wait)")
        post_slack_message("Calibration routine ended by user.")
        raise e

    except Exception as e:
        logging.warning("Unexpected error! Shutting down... (please wait)")
        post_slack_message(
            f"Calibration routine ended with error! {e}", mention_channel=True
        )
        raise e

    else:
        post_slack_message("Calibration routine ended successfully!")

    # Ensure gas mixer and water bath get turned off regardless of any unexpected errors
    finally:
        try:
            cosmobot_ssh_client.close()
        except Exception as e:
            logging.exception(e)

        _shut_down(gas_mixer_com_port, water_bath_com_port)
        post_slack_message("Calibration system shut down.")
