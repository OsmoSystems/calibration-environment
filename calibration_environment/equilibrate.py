import datetime
import logging
from time import sleep

import pandas as pd

from .configure import CalibrationConfiguration
from .data_logging import collect_data_to_csv, EquilibrationStatus


logger = logging.getLogger(__name__)

_TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION = 0.1  # degrees C
_TEMPERATURE_MINIMUM_STABLE_TIME = datetime.timedelta(minutes=5)

_DO_MAXIMUM_EQUILIBRATED_VARIATION = 0.03  # mg/l
_DO_MINIMUM_STABLE_TIME = datetime.timedelta(minutes=5)

_YSI_TEMPERATURE_FIELD_NAME = "YSI temperature (C)"
_YSI_DO_MGL_FIELD_NAME = "YSI DO (mg/L)"
_TIMESTAMP_FIELD_NAME = "timestamp"


def _is_field_equilibrated(sensor_data_log, field_name, max_variance, min_stable_time):
    oldest_timestamp = sensor_data_log[_TIMESTAMP_FIELD_NAME].min()
    newest_timestamp = sensor_data_log[_TIMESTAMP_FIELD_NAME].max()

    # ensure we have enough data
    if newest_timestamp - oldest_timestamp < min_stable_time:
        return False

    window_start_timestamp = newest_timestamp - min_stable_time
    data_window = sensor_data_log[
        sensor_data_log[_TIMESTAMP_FIELD_NAME] >= window_start_timestamp
    ]

    max_value = data_window[field_name].max()
    min_value = data_window[field_name].min()

    # round to get rid of floating point error
    variation = round(max_value - min_value, 5)
    return variation <= max_variance


def _wait_for_equilibration(
    setpoint,
    calibration_configuration,
    loop_count,
    equilibration_status,
    field_name,
    max_variation,
    min_stable_time,
):
    sensor_data_log = pd.DataFrame()

    while True:
        current_sensor_data = collect_data_to_csv(
            setpoint,
            calibration_configuration,
            loop_count=loop_count,
            equilibration_status=equilibration_status,
        )
        sensor_data_log = sensor_data_log.append(current_sensor_data, ignore_index=True)

        if _is_field_equilibrated(
            sensor_data_log, field_name, max_variation, min_stable_time
        ):
            return sensor_data_log

        sleep(5)


def wait_for_temperature_equilibration(
    calibration_configuration: CalibrationConfiguration,
    setpoint: pd.Series,
    loop_count: int,
) -> None:
    """
    Returns once temperature has not changed by more than
    _TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION degrees C for the last
    _TEMPERATURE_MINIMUM_STABLE_TIME.

    Args:
        calibration_configuration: CalibrationConfiguration object
        setpoint: pd.Series of setpoint for logging
        loop_count: loop iteration of the main calibration run loop
    """
    logger.info("waiting for water bath temperature equilibration")

    sensor_data_log = _wait_for_equilibration(
        setpoint,
        calibration_configuration,
        loop_count,
        EquilibrationStatus.TEMPERATURE,
        _YSI_TEMPERATURE_FIELD_NAME,
        _TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION,
        _TEMPERATURE_MINIMUM_STABLE_TIME,
    )

    current_temperature = sensor_data_log[_YSI_TEMPERATURE_FIELD_NAME].iloc[-1]
    logger.info(
        f"water bath temperature equilibrated (current temperature according to "
        f'"{_YSI_TEMPERATURE_FIELD_NAME}": {current_temperature}°C)'
    )


def wait_for_do_equilibration(
    calibration_configuration: CalibrationConfiguration,
    setpoint: pd.Series,
    loop_count: int,
) -> None:
    """
    Returns once DO level has not changed by more than
    _DO_MAXIMUM_EQUILIBRATED_VARIATION mg/l for the last
    _DO_MINIMUM_STABLE_TIME.

    Args:
        calibration_configuration: CalibrationConfiguration object
        setpoint: pd.Series of setpoint for logging
        loop_count: loop iteration of the main calibration run loop
    """

    logger.info("waiting for DO equilibration")

    sensor_data_log = _wait_for_equilibration(
        setpoint,
        calibration_configuration,
        loop_count,
        EquilibrationStatus.TEMPERATURE,
        _YSI_DO_MGL_FIELD_NAME,
        _DO_MAXIMUM_EQUILIBRATED_VARIATION,
        _DO_MINIMUM_STABLE_TIME,
    )

    current_do_mgl = sensor_data_log[_YSI_DO_MGL_FIELD_NAME].iloc[-1]
    logger.info(
        f"DO equilibrated (current DO level according to "
        f'"{_YSI_DO_MGL_FIELD_NAME}": {current_do_mgl} mg/l)'
    )
