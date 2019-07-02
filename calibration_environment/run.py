import sys
import enum
import logging
import queue
import threading
import time


from .equilibrate import (
    wait_for_temperature_equilibration,
    wait_for_gas_mixer_equilibration,
)
from .prepare import get_calibration_configuration
from .sensors import poll_data_to_csv

logging_format = "%(asctime)s [%(levelname)s]--- %(message)s"
logging.basicConfig(
    level=logging.INFO, format=logging_format, handlers=[logging.StreamHandler()]
)


class CalibrationState(enum.Enum):
    WAIT_FOR_TEMPERATURE_EQ = 0
    WAIT_FOR_GAS_MIXER_EQ = 1
    WAIT_FOR_SETPOINT_TIMEOUT = 2


class MemoryQueue(queue.Queue):
    """
        A basic FIFO queue which will return the last seen value if the queue is currently empty.
        Takes an initial_value in the constructor.
    """

    def __init__(self, initial_value=None, *args, **kwargs):
        queue.Queue.__init__(self, *args, **kwargs)
        self.last_value = initial_value

    def get(self):
        if not self.empty():
            self.last_value = self.get()
        return self.last_value


def run(cli_args=None):
    try:
        if cli_args is None:
            # First argument is the name of the command itself, not an "argument" we want to parse
            cli_args = sys.argv[1:]
        # Parse the configuration parameters from cli args
        calibration_configuration = get_calibration_configuration(cli_args)

        logging.info(f"Logging sensor data to {calibration_configuration.output_csv}")

        if calibration_configuration.dry_run:
            from .drivers.stubs import gas_mixer
            from .drivers.stubs import water_bath
        else:
            from .drivers import gas_mixer  # type: ignore # already defined warning
            from .drivers import water_bath  # type: ignore # already defined warning

        water_bath_com_port = calibration_configuration.com_port_args["water_bath"]
        gas_mixer_com_port = calibration_configuration.com_port_args["gas_mixer"]

        water_bath.initialize(water_bath_com_port)

        sequence_iteration_count = 0

        # Initialize queues to send state updates to data collection thread
        setpoint_queue: MemoryQueue = MemoryQueue(
            calibration_configuration.setpoints.loc[0]
        )
        equilibration_state_queue: MemoryQueue = MemoryQueue(
            CalibrationState.WAIT_FOR_TEMPERATURE_EQ
        )
        sequence_iteration_count_queue: MemoryQueue = MemoryQueue(
            sequence_iteration_count
        )
        end_data_collection_signal = threading.Event()

        data_collection_thread = threading.Thread(
            target=poll_data_to_csv,
            kwargs={
                "calibration_configuration": calibration_configuration,
                "setpoint_queue": setpoint_queue,
                "sequence_iteration_count_queue": sequence_iteration_count_queue,
                "equilibration_state_queue": equilibration_state_queue,
                "end_data_collection_signal": end_data_collection_signal,
            },
        )

        data_collection_thread.start()

        while True:
            sequence_iteration_count_queue.put(sequence_iteration_count)

            for i, setpoint in calibration_configuration.setpoints.iterrows():

                # TODO: Equilibration Procedure Software Implementation
                # https://app.asana.com/0/1123279738062524/1128578386488633

                setpoint_queue.put(setpoint)
                equilibration_state_queue.put(CalibrationState.WAIT_FOR_TEMPERATURE_EQ)
                # Set water bath temperature set point
                water_bath.send_command_and_parse_response(
                    water_bath_com_port,
                    command_name="Set Setpoint",
                    data=setpoint["temperature"],
                )
                wait_for_temperature_equilibration(water_bath, water_bath_com_port)

                # Set the gas mixer ratio
                equilibration_state_queue.put(CalibrationState.WAIT_FOR_GAS_MIXER_EQ)
                gas_mixer.start_constant_flow_mix(
                    gas_mixer_com_port,
                    setpoint["flow_rate_slpm"],
                    setpoint["o2_target_gas_fraction"],
                    calibration_configuration.o2_source_gas_fraction,
                )
                wait_for_gas_mixer_equilibration(gas_mixer, gas_mixer_com_port)

                equilibration_state_queue.put(
                    CalibrationState.WAIT_FOR_SETPOINT_TIMEOUT
                )
                time.sleep(calibration_configuration.setpoint_wait_time)

            if not calibration_configuration.loop:
                break

            # Increment so we know which iteration we're on in the logs
            sequence_iteration_count += 1

    finally:
        gas_mixer.stop_flow(gas_mixer_com_port)
        # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
        # water_bath.shutdown(water_bath_com_port)

        # Send an event to data collection thread and wait for it to exit
        end_data_collection_signal.set()
        data_collection_thread.join()
