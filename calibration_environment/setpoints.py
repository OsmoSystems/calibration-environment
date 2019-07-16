import pandas as pd

from .drivers.gas_mixer import get_mix_validation_errors
from .drivers.water_bath import get_temperature_validation_errors


def _get_setpoint_validation_errors(setpoint, o2_source_gas_fraction):
    return pd.concat(
        [
            get_mix_validation_errors(
                setpoint["flow_rate_slpm"],
                o2_source_gas_fraction,
                setpoint["o2_target_gas_fraction"],
            ),
            get_temperature_validation_errors(setpoint["temperature"]),
        ]
    )


def validate_setpoints(setpoints, o2_source_gas_fraction):
    setpoint_errors = setpoints.apply(
        _get_setpoint_validation_errors, axis=1, args=(o2_source_gas_fraction,)
    )

    rows_with_errors = setpoint_errors.sum(axis=1) > 0

    return setpoint_errors[rows_with_errors]


def read_setpoint_sequence_file(sequence_csv_filepath):
    setpoints = pd.read_csv(sequence_csv_filepath)
    return setpoints
