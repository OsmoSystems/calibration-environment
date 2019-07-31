import logging
from typing import Dict, List

import serial

from calibration_environment.drivers import gas_mixer, water_bath


logger = logging.getLogger(__name__)


class CalibrationSequenceAbort(Exception):
    # Raised when one or more calibration systems is not good to go
    pass


def _get_and_log_any_exceptions(
    title, check_function, expected_exceptions
) -> List[Exception]:
    try:
        check_function()
    except expected_exceptions as e:
        logger.exception(f"{title} status check failed")
        return [e]
    return []


def check_status(com_ports: Dict[str, str]) -> None:
    """ Check that the calibration systems are good to go, raising CalibrationSequenceAbort if not
    Currently checks water bath status registers for warnings and errors, and gas mixer status for low feed pressure

    Args:
        com_ports: dict of gas_mixer and water_bath COM ports

    Returns: None

    Raises:
        CalibrationSequenceAbort if one or more of the calibration systems is not good to go

    Logs:
        Any traceback encountered at exception level, or a success message at debug level

    """
    gas_mixer_exceptions = _get_and_log_any_exceptions(
        "Gas mixer",
        check_function=lambda: gas_mixer.assert_status_ok_with_retry(
            com_ports["gas_mixer"]
        ),
        expected_exceptions=(
            serial.SerialException,
            gas_mixer.UnexpectedMixerResponse,
            gas_mixer.GasMixerStatusError,
        ),
    )
    water_bath_exceptions = _get_and_log_any_exceptions(
        "Water bath",
        check_function=lambda: water_bath.assert_status_ok(com_ports["water_bath"]),
        expected_exceptions=(
            serial.SerialException,
            water_bath.exceptions.InvalidResponse,
            water_bath.exceptions.WaterBathStatusError,
        ),
    )

    exceptions = gas_mixer_exceptions + water_bath_exceptions

    if exceptions:
        raise CalibrationSequenceAbort(exceptions)
    else:
        logger.debug("Clean status check")
