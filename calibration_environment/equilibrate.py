import datetime
import logging
from time import sleep

import pandas as pd

from .configure import CalibrationConfiguration
from .data_logging import collect_data_to_csv, EquilibrationStatus


logger = logging.getLogger(__name__)

_TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION = 0.1  # degrees C
_TEMPERATURE_MINIMUM_STABLE_TIME = datetime.timedelta(minutes=5)

_YSI_TEMPERATURE_FIELD_NAME = "YSI temperature (C)"
_TIMESTAMP_FIELD_NAME = "timestamp"


def _is_temperature_equilibrated(sensor_data_log):
    oldest_timestamp = sensor_data_log[_TIMESTAMP_FIELD_NAME].min()
    newest_timestamp = sensor_data_log[_TIMESTAMP_FIELD_NAME].max()

    # ensure we have enough data
    if newest_timestamp - oldest_timestamp < _TEMPERATURE_MINIMUM_STABLE_TIME:
        return False

    window_start_timestamp = newest_timestamp - _TEMPERATURE_MINIMUM_STABLE_TIME
    data_window = sensor_data_log[
        sensor_data_log[_TIMESTAMP_FIELD_NAME] >= window_start_timestamp
    ]

    max_temperature = data_window[_YSI_TEMPERATURE_FIELD_NAME].max()
    min_temperature = data_window[_YSI_TEMPERATURE_FIELD_NAME].min()

    # round to get rid of floating point error
    variation = round(max_temperature - min_temperature, 3)
    return variation <= _TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION


def wait_for_temperature_equilibration(
    calibration_configuration: CalibrationConfiguration, setpoint: pd.Series
) -> None:
    """
    Returns once temperature has not changed by more than
    _TEMPERATURE_MAXIMUM_EQUILIBRATED_VARIATION degrees C for the last
    _TEMPERATURE_MINIMUM_STABLE_TIME.

    Args:
        calibration_configuration: CalibrationConfiguration object
        setpoint: pd.Series of setpoint for logging
    """
    logger.info("waiting for water bath temperature equilibration")

    sensor_data_log = pd.DataFrame()

    while True:
        current_sensor_data = collect_data_to_csv(
            setpoint,
            calibration_configuration.com_ports,
            equilibration_status=EquilibrationStatus.TEMPERATURE,
        )
        sensor_data_log = sensor_data_log.append(current_sensor_data, ignore_index=True)

        if _is_temperature_equilibrated(sensor_data_log):
            current_temperature = current_sensor_data[_YSI_TEMPERATURE_FIELD_NAME]
            logger.info(
                f"water bath temperature equilibrated (current temperature according to "
                f'"{_YSI_TEMPERATURE_FIELD_NAME}": {current_temperature}°C)'
            )
            return

        sleep(5)


def wait_for_gas_mixer_equilibration(
    calibration_configuration: CalibrationConfiguration, setpoint: pd.Series
) -> None:
    # TODO: Equilibration Procedure Software Implementation: Gas mixer
    # https://app.asana.com/0/819671808102776/1128578386488633/f

    return
