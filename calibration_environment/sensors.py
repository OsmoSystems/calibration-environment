import time
from datetime import datetime

import pandas as pd

from .equilibrate import check_temperature_equilibrated, check_gas_mixer_equilibrated

from .drivers import gas_mixer
from .drivers import water_bath


def get_all_sensor_data_stub(com_port_args, retry_count=0):
    return pd.Series({"data": 1}).add_prefix("stub ")


def get_all_sensor_data(com_port_args, retry_count=0):
    gas_mixer_status = gas_mixer.get_mixer_status(
        com_port_args["gas_mixer"]
    ).add_prefix("gas mixer ")

    gas_ids = gas_mixer.get_gas_ids(com_port_args["gas_mixer"]).add_suffix(" gas ID")

    water_bath_status = pd.Series(
        {
            "internal temperature (C)": water_bath.send_command_and_parse_response(
                com_port_args["water_bath"], "Read Internal Temperature"
            ),
            "external sensor temperature (C)": water_bath.send_command_and_parse_response(
                com_port_args["water_bath"], "Read External Sensor"
            ),
        }
    ).add_prefix("water bath ")

    return pd.concat([gas_mixer_status, gas_ids, water_bath_status])


def collect_data_to_csv(
    serial_lock,
    setpoint,
    calibration_configuration,
    equilibration_state,
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
    # Use the stub if not using real sensors
    sensor_data_getter = (
        get_all_sensor_data_stub
        if calibration_configuration.dry_run
        else get_all_sensor_data
    )

    # Read from each sensor and add to the DataFrame
    with serial_lock:
        sensor_data = sensor_data_getter(calibration_configuration.com_port_args)

    row = pd.Series(
        {
            "iteration": sequence_iteration_count,
            "setpoint temperature": setpoint["temperature"],
            "setpoint flow rate": setpoint["flow_rate_slpm"],
            "setpoint target gas fraction": setpoint["o2_target_gas_fraction"],
            "o2 source gas fraction": calibration_configuration.o2_source_gas_fraction,
            "timestamp": datetime.now(),
            "equilibration state": equilibration_state.name,
            "temperature equilibrated": check_temperature_equilibrated(
                water_bath, calibration_configuration.com_port_args["water_bath"]
            ),
            "gas mixer equilibrated": check_gas_mixer_equilibrated(
                gas_mixer, calibration_configuration.com_port_args["gas_mixer"]
            ),
            **dict(sensor_data),
        }
    )

    # Use mode="a" to append the row to the file
    pd.DataFrame(row).T.to_csv(
        calibration_configuration.output_csv,
        index=False,
        header=write_headers_to_file,
        mode="a",
    )


def poll_data_to_csv(
    serial_lock,
    calibration_configuration,
    setpoint_queue,
    sequence_iteration_count_queue,
    equilibration_state_queue,
    end_data_collection_signal,
):
    write_headers_to_file = True

    while not end_data_collection_signal.is_set():

        collect_data_to_csv(
            serial_lock,
            setpoint_queue.get(),
            calibration_configuration,
            equilibration_state_queue.get(),
            sequence_iteration_count_queue.get(),
            write_headers_to_file=write_headers_to_file,
        )
        write_headers_to_file = False

        if end_data_collection_signal.is_set():
            return

        time.sleep(calibration_configuration.collection_interval)
