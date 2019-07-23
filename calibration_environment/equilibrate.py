import logging
from time import sleep, time

from .drivers import water_bath


logger = logging.getLogger(__name__)

_ONE_MINUTE_IN_SECONDS = 60
_TEMPERATURE_THRESHOLD = 0.1  # degrees C
_TEMPERATURE_MINIMUM_TIME = 5 * _ONE_MINUTE_IN_SECONDS


def wait_for_temperature_equilibration(water_bath_com_port: str) -> None:
    """
    Returns once temperature has not changed by more than
    _TEMPERATURE_THRESHOLD degrees C for the last
    _TEMPERATURE_MINIMUM_TIME seconds.

    Args:
        water_bath_com_port: COM port for the water bath serial interface
    """

    logger.info("waiting for water bath temperature equilibration")

    temperature_log = []
    logging_start_time = time()

    while True:
        current_temperature = water_bath.send_command_and_parse_response(
            water_bath_com_port, "Read Internal Sensor"
        )
        now = time()
        temperature_log.append((now, current_temperature))

        # TODO log full set of sensor data to csv
        logger.debug(f"current temperature: {current_temperature}")

        has_been_logging_for_min_time = (
            now - logging_start_time >= _TEMPERATURE_MINIMUM_TIME
        )
        if has_been_logging_for_min_time:
            while (
                temperature_log
                and now - temperature_log[0][0] > _TEMPERATURE_MINIMUM_TIME
            ):
                temperature_log.pop(0)

            temperatures = [i[1] for i in temperature_log]
            if max(temperatures) - min(temperatures) <= _TEMPERATURE_THRESHOLD:
                logger.info(
                    f"achieved water bath temperature equilibration (current temperature: {current_temperature}°C)"
                )
                return

        sleep(1)


def wait_for_gas_mixer_equilibration(gas_mixer_com_port):
    # TODO: Equilibration Procedure Software Implementation: Gas mixer
    # https://app.asana.com/0/819671808102776/1128578386488633/f

    return
