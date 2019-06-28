import os
import time
from datetime import datetime

import pandas as pd

from .equilibrate import wait_for_temperature, wait_for_gas_mixer
from .prepare import get_calibration_configuration

# This works for now since the only windows computer is the only device with
# real sensors hooked up. Need to reconcile with this vs. the --dry_run cli flag
if os.name == "nt":
    from .drivers import gas_mixer, NESLAB_RTE_7
else:
    from .drivers.stubs import gas_mixer, NESLAB_RTE_7  # type: ignore


def get_all_sensor_data_stub(com_port_args):
    return pd.Series({"stub_data": 1})


def get_all_sensor_data(com_port_args):
    gas_mixer_status = gas_mixer.get_mixer_status(com_port_args["gas_mixer"])
    gas_ids = gas_mixer.get_gas_ids(com_port_args["gas_mixer"])

    water_bath_status_part_1 = NESLAB_RTE_7.get_status_func_1(
        com_port_args["water_bath"]
    )
    water_bath_status_part_2 = NESLAB_RTE_7.get_status_func_2(
        com_port_args["water_bath"]
    )

    return pd.concat(
        [gas_mixer_status, gas_ids, water_bath_status_part_1, water_bath_status_part_2]
    )


def run(cli_args):
    # Parse the configuration parameters from cli args
    calibration_configuration = get_calibration_configuration(cli_args)

    write_headers_to_file = True

    while True:
        for _, setpoint in calibration_configuration.setpoints.iterrows():
            water_bath_com_port = calibration_configuration.com_port_args["water_bath"]

            gas_mixer_com_port = calibration_configuration.com_port_args["gas_mixer"]

            # Set the water bath temperature
            NESLAB_RTE_7.set_temperature(water_bath_com_port, setpoint["temperature"])
            # Magical function that returns when the system is ready, or has an error
            wait_for_temperature(water_bath_com_port)

            # Set the gax mixer ratio
            gas_mixer.start_constant_flow_mix(
                gas_mixer_com_port,
                setpoint["flow_rate_slpm"],
                setpoint["o2_target_gas_fraction"],
                calibration_configuration.o2_source_gas_fraction,
            )

            wait_for_gas_mixer(gas_mixer_com_port)

            for i in range(calibration_configuration.read_count):

                # Use the stub if not using real sensors
                sensor_data_getter = (
                    get_all_sensor_data_stub
                    if calibration_configuration.dry_run
                    else get_all_sensor_data
                )

                # Read from each sensor and add to the DataFrame
                sensor_data = sensor_data_getter(
                    calibration_configuration.com_port_args
                )

                row = pd.Series(
                    {
                        "setpoint_temperature": setpoint["temperature"],
                        "setpoint_flow_rate": setpoint["flow_rate_slpm"],
                        "setpoint_target_gas_fraction": setpoint[
                            "o2_target_gas_fraction"
                        ],
                        "o2_source_gas_fraction": calibration_configuration.o2_source_gas_fraction,
                        "timestamp": datetime.now(),
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

                write_headers_to_file = False

                # Wait to collect the next data point
                time.sleep(calibration_configuration.collection_wait_time)

        # Not a hard requirement to configurably loop forever
        if not calibration_configuration.loop:
            gas_mixer.stop_flow(gas_mixer_com_port)
            NESLAB_RTE_7.shutdown(water_bath_com_port)
            return
