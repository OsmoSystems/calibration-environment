from datetime import datetime

import pandas as pd

from .configure import CalibrationConfiguration
from .drivers import gas_mixer
from .drivers import water_bath
from .drivers import ysi


def get_all_sensor_data(com_ports):
    gas_mixer_status = gas_mixer.get_mixer_status_with_retry(
        com_ports["gas_mixer"]
    ).add_prefix("gas mixer ")

    gas_ids = gas_mixer.get_gas_ids_with_retry(com_ports["gas_mixer"]).add_suffix(
        " gas ID"
    )

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


def collect_equilibration_data_to_csv(
    calibration_configuration: CalibrationConfiguration, sensor_data: pd.Series
) -> None:
    row = pd.DataFrame([{"timestamp": datetime.now(), **dict(sensor_data)}]).sort_index(
        axis=1
    )  # Sort the index so columns are always in the same order

    with open(calibration_configuration.equilibration_csv_filepath, "a") as csv_file:
        # TODO update other function to use this for header?
        is_file_empty = csv_file.tell() == 0
        row.to_csv(csv_file, index=False, header=is_file_empty, mode="a")
