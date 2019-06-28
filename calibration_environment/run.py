import sys
import time
import enum
from datetime import datetime

import pandas as pd

from .equilibrate import check_temperature_equilibrated, check_gas_mixer_equilibrated
from .prepare import get_calibration_configuration


class CalibrationState(enum.Enum):
    WAIT_FOR_TEMPERATURE_EQ = 0
    WAIT_FOR_GAS_MIXER_EQ = 1
    WAIT_FOR_SETPOINT_TIMEOUT = 2


DATA_COLLECTION_INTERVAL_SECONDS = 60


def get_all_sensor_data_stub(gas_mixer, water_bath, com_port_args):
    return pd.Series({"data": 1}).add_prefix("stub ")


def get_all_sensor_data(gas_mixer, water_bath, com_port_args):
    gas_mixer_status = gas_mixer.get_mixer_status(
        com_port_args["gas_mixer"]
    ).add_prefix("gas mixer ")

    gas_ids = gas_mixer.get_gas_ids(com_port_args["gas_mixer"]).add_prefix("gas mixer ")

    # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
    # water_bath_status = water_bath.get_temperature(com_port_args["water_bath"]).add_prefix("NESLAB RTE 7")

    return pd.concat([gas_mixer_status, gas_ids])


def collect_data_to_csv(
    gas_mixer,
    water_bath,
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
    sensor_data = sensor_data_getter(
        calibration_configuration.com_port_args, gas_mixer, water_bath
    )

    row = pd.Series(
        {
            "iteration": sequence_iteration_count,
            "setpoint temperature": setpoint["temperature"],
            "setpoint flow rate": setpoint["flow_rate_slpm"],
            "setpoint target gas fraction": setpoint["o2_target_gas_fraction"],
            "o2 source gas fraction": calibration_configuration.o2_source_gas_fraction,
            "timestamp": datetime.now(),
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


def run(cli_args=None):
    try:
        if cli_args is None:
            # First argument is the name of the command itself, not an "argument" we want to parse
            cli_args = sys.argv[1:]
        # Parse the configuration parameters from cli args
        calibration_configuration = get_calibration_configuration(cli_args)

        if calibration_configuration.dry_run:
            from .drivers.stubs import gas_mixer

            # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
            water_bath = None
        else:
            from .drivers import gas_mixer  # type: ignore # already defined warning

            # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
            water_bath = None

        water_bath_com_port = calibration_configuration.com_port_args["water_bath"]

        gas_mixer_com_port = calibration_configuration.com_port_args["gas_mixer"]

        sequence_iteration_count = 0
        write_headers_to_file = True

        while True:

            for i, setpoint in calibration_configuration.setpoints.iterrows():

                # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
                # water_bath.set_temperature(water_bath_com_port, setpoint["temperature"])

                CALIBRATION_STATE = CalibrationState.WAIT_FOR_TEMPERATURE_EQ

                while True:
                    collect_data_to_csv(
                        gas_mixer,
                        water_bath,
                        setpoint,
                        calibration_configuration,
                        sequence_iteration_count=sequence_iteration_count,
                        write_headers_to_file=write_headers_to_file,
                    )
                    write_headers_to_file = False

                    if CALIBRATION_STATE == CalibrationState.WAIT_FOR_TEMPERATURE_EQ:
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
                            CALIBRATION_STATE = CalibrationState.WAIT_FOR_GAS_MIXER_EQ

                    elif CALIBRATION_STATE == CalibrationState.WAIT_FOR_GAS_MIXER_EQ:
                        gas_mixer_equilibrated = check_gas_mixer_equilibrated(
                            gas_mixer, gas_mixer_com_port
                        )
                        if gas_mixer_equilibrated:
                            # Start tracking how long to stay at this setpoint
                            setpoint_equilibration_start = datetime.now()
                            CALIBRATION_STATE = (
                                CalibrationState.WAIT_FOR_SETPOINT_TIMEOUT
                            )
                            # TODO: Reduce or stop gas mixer flow rate

                    elif (
                        CALIBRATION_STATE == CalibrationState.WAIT_FOR_SETPOINT_TIMEOUT
                    ):
                        setpoint_duration = (
                            datetime.now() - setpoint_equilibration_start
                        )
                        if (
                            setpoint_duration.total_seconds()
                            > calibration_configuration.collection_wait_time
                        ):
                            break
                    else:
                        raise ValueError(
                            f"Invalid calibration state {CALIBRATION_STATE}"
                        )

                    # Wait before collecting next datapoint
                    time.sleep(DATA_COLLECTION_INTERVAL_SECONDS)

            # Increment so we know which iteration we're on in the logs
            sequence_iteration_count += 1

            if not calibration_configuration.loop:
                break
    finally:
        # TODO: https://app.asana.com/0/819671808102776/1128811014542923/f
        # gas_mixer.stop_flow(gas_mixer_com_port)
        # water_bath.shutdown(water_bath_com_port)
        pass
