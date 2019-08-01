import logging
from typing import Collection

import numpy as np
import pandas as pd

from calibration_environment.setpoints.validate import get_validation_errors
from calibration_environment.setpoints.constants import (
    DEFAULT_FLOW_RATE_SLPM,
    AVERAGE_SYSTEM_PRESSURE_MMHG,
)


logger = logging.getLogger(__name__)


def _sort_do_within_temperature(
    temperature_sweep: pd.DataFrame, temperatures_with_ascending_do: Collection[float]
) -> pd.DataFrame:
    """ Sort the DO values within a single temperature

    params:
        temperature_sweep: DataFrame of setpoints at one temperature
        temperatures_with_ascending_do: collection of temperatures - if this contains the temperature of
            temperature_sweep, we'll sort in increasing order of oxygen level; otherwise we'll sort descending.
    """
    current_temperature = temperature_sweep["temperature"].iloc[0]

    return temperature_sweep.sort_values(
        "o2_fraction", ascending=current_temperature in temperatures_with_ascending_do
    )


def get_unordered_setpoints(
    min_temperature: float,
    max_temperature,
    temperatures_setpoint_count,
    min_do_mmhg,
    max_do_mmhg,
    DO_setpoint_count,
):
    """
    Create a DataFrame of all the combinations of DO + temperature in the provided parameters.
    """

    # Get evenly spaced setpoints
    temperature_setpoints = np.linspace(
        min_temperature, max_temperature, temperatures_setpoint_count
    )
    DO_setpoints = np.linspace(min_do_mmhg, max_do_mmhg, DO_setpoint_count)

    setpoints = pd.DataFrame(
        [
            (temperature, DO)
            for temperature in temperature_setpoints
            for DO in DO_setpoints
        ],
        columns=["temperature", "DO (mmHg)"],
    )

    # Calculate O2 fraction based on mmHg
    # We include both because the calibration program expects a fraction, but mmHg is a little nicer for humans
    setpoints["o2_fraction"] = setpoints["DO (mmHg)"] / AVERAGE_SYSTEM_PRESSURE_MMHG

    return setpoints


def order_setpoints(sweep: pd.DataFrame, start_high_do=True, start_high_temp=False):
    """ Reorder DO and Temperature setpoints to optimize for amount of time taken in transitions.
    Sorts by temperature and then alternates increasing and decreasing DO to minimize the delta between setpoints.

    Params:
        sweep: sequence of setpoints to rearrange
        start_high_do: whether to start with a high DO level (to more quickly equilibrate with atmosphere)
        start_high_temp: whether to start with a high temperature
    """
    sweep_with_temperature_ordering = sweep.sort_values(
        "temperature", ascending=not start_high_temp
    )

    # If we're starting high, odd-indexed temperatures (1,3,...) will have ascending DO
    # otherwise, even-indexed (0,2,...) sweeps will ascend in DO
    index_of_first_temperature_with_ascending_do = 1 if start_high_do else 0
    temperatures_with_ascending_do = sweep_with_temperature_ordering[
        "temperature"
    ].unique()[index_of_first_temperature_with_ascending_do::2]

    return (
        sweep_with_temperature_ordering.groupby(
            "temperature",
            sort=False,  # Preserve the order the temperature groups are already in
            as_index=False,
        )
        .apply(
            _sort_do_within_temperature,
            temperatures_with_ascending_do=temperatures_with_ascending_do,
        )
        .reset_index(drop=True)
    )


def remove_invalid_points(sweep, o2_source_gas_o2_fraction):
    errors = get_validation_errors(
        sweep, o2_source_gas_o2_fraction=o2_source_gas_o2_fraction
    )

    if len(errors):
        logger.info(f"{len(errors)} un-hittable setpoints removed:\n{errors}")

    return sweep.drop(errors.index)


def create_sweep(
    min_temperature: float,
    max_temperature: float,
    temperatures_setpoint_count: int,
    min_do_mmhg: float,
    max_do_mmhg: float,
    do_setpoint_count: int,
    o2_source_gas_o2_fraction: float,
    hold_time_seconds: int,
    start_high_temp: bool = False,
    start_high_do: bool = True,
    flow_rate_slpm: float = DEFAULT_FLOW_RATE_SLPM,
) -> pd.DataFrame:
    """ Create a sweep of setpoints across a range of temperatures and oxygen levels

    Args:
        min_temperature: lowest temperature setpoint to hit
        max_temperature: highest temperature setpoint to hit
        temperatures_setpoint_count: number of distinct temperatures to include
        min_do_mmhg: lowest DO value to hit (mmHg)
        max_do_mmhg: highest DO value to hit (mmHg)
        do_setpoint_count: number of distinct DO values to include
        o2_source_gas_o2_fraction: fraction of oxygen in oxygen source gas for this run
        start_high_temp: if True, hit the highest temperature setpoint first, and vice versa (default=False).
        start_high_do: if True (default), start sweep with a high-DO setpoint (to more quickly equilibrate if
            environment is starting at atmospheric conditions). start_high_do=False produces a sequence that will
            equilibrate more quickly if the calibration environment already has low DO.

    Returns:
        pd.DataFrame of setpoints with the following columns:
            temperature: The desired setpoint temperature in degrees Celsius.
            flow_rate_slpm: The desired setpoint flow rate in Standard Liters Per Minute
            o2_fraction: The desired O2 fraction of the output gas mix.
            DO (mmHg): partial pressure of DO (directly proportional to o2_fraction, provided for human friendliness)
            hold_time: The amount of time in seconds to hold at this setpoint for data collection.
    """
    raw_setpoints = get_unordered_setpoints(
        min_temperature=min_temperature,
        max_temperature=max_temperature,
        temperatures_setpoint_count=temperatures_setpoint_count,
        min_do_mmhg=min_do_mmhg,
        max_do_mmhg=max_do_mmhg,
        DO_setpoint_count=do_setpoint_count,
    )

    raw_setpoints["flow_rate_slpm"] = flow_rate_slpm
    raw_setpoints["hold_time"] = hold_time_seconds

    ordered_setpoints = order_setpoints(
        sweep=raw_setpoints,
        start_high_do=start_high_do,
        start_high_temp=start_high_temp,
    )

    cleaned_ordered_setpoints = remove_invalid_points(
        ordered_setpoints, o2_source_gas_o2_fraction=o2_source_gas_o2_fraction
    )

    return cleaned_ordered_setpoints
