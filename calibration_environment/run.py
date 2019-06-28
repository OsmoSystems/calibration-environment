import time
from datetime import datetime

import pandas as pd

from .equilibrate import check_temperature_equilibrated, check_gas_mixer_equilibrated
from .prepare import get_calibration_configuration

# Calibration states
WAIT_FOR_T_EQ = 0
WAIT_FOR_GM_EQ = 1
WAIT_FOR_SETPOINT_TIMEOUT = 2

DATA_COLLECTION_INTERVAL = 60


def prefix_series_index(prefix: str, data: pd.Series) -> pd.Series:
    data.index = prefix + data.index
    return data


def get_all_sensor_data_stub(gas_mixer, water_bath, com_port_args):
    return prefix_series_index("Stub ", pd.Series({"data": 1}))


def get_all_sensor_data(gas_mixer, water_bath, com_port_args):
    gas_mixer_status = prefix_series_index(
        "Gas Mixer ", gas_mixer.get_mixer_status(com_port_args["gas_mixer"])
    )
    gas_ids = prefix_series_index(
        "Gas Mixer ", gas_mixer.get_gas_ids(com_port_args["gas_mixer"])
    )

    # TODO: waterbath interface
    # water_bath_status = prefix_series_index(
    #     "NESLAB RTE 7 ",
    #     water_bath.get_temperature(com_port_args["water_bath"])
    # )

    return pd.concat([gas_mixer_status, gas_ids])


def collect_data(
    gas_mixer,
    water_bath,
    setpoint,
    calibration_configuration,
    sequence_iteration_count=0,
    write_headers_to_file=True,
):
    # Use the stub if not using real sensors
    sensor_data_getter = (
        get_all_sensor_data_stub
        if calibration_configuration.dry_run
        else get_all_sensor_data
    )

    # Read from each sensor and add to the DataFrame
    sensor_data = sensor_data_getter(
        calibration_configuration.com_port_args, gas_mixer, water_bath
    )

    row = pd.Series(
        {
            "iteration": sequence_iteration_count,
            "setpoint_temperature": setpoint["temperature"],
            "setpoint_flow_rate": setpoint["flow_rate_slpm"],
            "setpoint_target_gas_fraction": setpoint["o2_target_gas_fraction"],
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


def run(cli_args):
    # Parse the configuration parameters from cli args
    calibration_configuration = get_calibration_configuration(cli_args)

    if calibration_configuration.dry_run:
        from .drivers.stubs import gas_mixer

        # TODO: add waterbath interface
        water_bath = None
    else:
        from .drivers import gas_mixer  # type: ignore # shadow assignment warning

        # TODO: add waterbath interface
        water_bath = None

    water_bath_com_port = calibration_configuration.com_port_args["water_bath"]

    gas_mixer_com_port = calibration_configuration.com_port_args["gas_mixer"]

    sequence_iteration_count = 0
    write_headers_to_file = True

    while True:

        for i, setpoint in calibration_configuration.setpoints.iterrows():

            # TODO: Set the water bath temperature
            # water_bath.set_temperature(water_bath_com_port, setpoint["temperature"])

            CALIBRATION_STATE = WAIT_FOR_T_EQ

            while True:
                collect_data(
                    gas_mixer,
                    water_bath,
                    setpoint,
                    calibration_configuration,
                    sequence_iteration_count=sequence_iteration_count,
                    write_headers_to_file=write_headers_to_file,
                )
                write_headers_to_file = False

                if CALIBRATION_STATE == WAIT_FOR_T_EQ:
                    temperature_equilibrated = check_temperature_equilibrated(
                        water_bath, water_bath_com_port
                    )
                    if temperature_equilibrated:
                        # Set the gax mixer ratio
                        gas_mixer.start_constant_flow_mix(
                            gas_mixer_com_port,
                            setpoint["flow_rate_slpm"],
                            setpoint["o2_target_gas_fraction"],
                            calibration_configuration.o2_source_gas_fraction,
                        )
                        CALIBRATION_STATE = WAIT_FOR_GM_EQ

                elif CALIBRATION_STATE == WAIT_FOR_GM_EQ:
                    gas_mixer_equilibrated = check_gas_mixer_equilibrated(
                        gas_mixer, gas_mixer_com_port
                    )
                    if gas_mixer_equilibrated:
                        # Start tracking how long to stay at this setpoint
                        setpoint_equilibration_start = datetime.now()
                        CALIBRATION_STATE = WAIT_FOR_SETPOINT_TIMEOUT

                elif CALIBRATION_STATE == WAIT_FOR_SETPOINT_TIMEOUT:
                    setpoint_duration = datetime.now() - setpoint_equilibration_start
                    if (
                        setpoint_duration.total_seconds()
                        > calibration_configuration.collection_wait_time
                    ):
                        break
                else:
                    raise ValueError(f"Ivalid calibration state {CALIBRATION_STATE}")

                # Wait before collecting next datapoint
                time.sleep(DATA_COLLECTION_INTERVAL)

        # Increment so we know which iteration we're on in the logs
        sequence_iteration_count += 1

        if not calibration_configuration.loop:
            gas_mixer.stop_flow(gas_mixer_com_port)
            # TODO
            # water_bath.shutdown(water_bath_com_port)
            return
