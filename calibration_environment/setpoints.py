import pandas as pd

from .drivers.gas_mixer import get_mix_validation_errors
from .drivers.water_bath import get_temperature_validation_errors


def _get_setpoint_validation_errors(
    setpoint: pd.DataFrame, o2_source_gas_fraction: float
) -> pd.Series:

    all_errors = get_mix_validation_errors(
        setpoint["flow_rate_slpm"], o2_source_gas_fraction, setpoint["o2_fraction"]
    ) + get_temperature_validation_errors(setpoint["temperature"])

    return all_errors


def get_validation_errors(
    setpoints: pd.DataFrame, o2_source_gas_o2_fraction: float
) -> pd.DataFrame:
    """ Run validation checks against all setpoints and return all errors

        Args:
            setpoints: A DataFrame with setpoint definitions
            o2_source_gas_o2_fraction: A float specifying the O2 source gas O2 fraction

        Returns:
            A DataFrame with setpoints containing errors where columns represent errors
            and a True value indicates the setpoint has that error.
            The original DataFrame index is preserved.
    """
    setpoint_errors = setpoints.apply(
        _get_setpoint_validation_errors, axis=1, args=(o2_source_gas_o2_fraction,)
    )

    errors_present_selector = setpoint_errors.apply(lambda errors: len(errors) > 0)
    return setpoint_errors[errors_present_selector]


def read_setpoint_sequence_file(sequence_csv_filepath: str) -> pd.DataFrame:
    setpoints = pd.read_csv(sequence_csv_filepath)
    return setpoints
