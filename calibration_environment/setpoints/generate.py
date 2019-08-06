import logging

import numpy as np
import pandas as pd

from calibration_environment.setpoints.validate import get_validation_errors
from calibration_environment.setpoints.constants import (
    DEFAULT_FLOW_RATE_SLPM,
    AVERAGE_SYSTEM_PRESSURE_MMHG,
)


logger = logging.getLogger(__name__)


def generate_ordered_setpoints(
    min_temperature: float,
    max_temperature: float,
    temperatures_setpoint_count: int,
    min_do_mmhg: float,
    max_do_mmhg: float,
    do_setpoint_count: int,
    start_high_temperature: bool = False,
    start_high_do: bool = True,
) -> pd.DataFrame:
    """ Create a DataFrame of all the combinations of DO + temperature in the provided parameters, ordered efficiently.
    Efficient ordering minimizes equilibration time. In our efficient setpoint ordering:
    * temperatures are in monotonically increasing or decreasing order (based on the start_high_temperature param)
    * DO also changes monotonically within each temperature.
        * where one temperature starts with high DO, the next temperature will start with the same high DO value,
            to avoid unnecessary equilibration time.

    Args:
        min_temperature: lowest temperature setpoint to hit
        max_temperature: highest temperature setpoint to hit
        temperatures_setpoint_count: number of distinct temperatures to include
        min_do_mmhg: lowest DO value to hit (approximate mmHg)
        max_do_mmhg: highest DO value to hit (approximate mmHg)
             DO mmHg values are approximate because total pressure of the chamber may fluctuate, and we only actually
             control the percentage of oxygen present.
        do_setpoint_count: number of distinct DO values to include
        start_high_temperature: if True (default=False), hit the highest temperature setpoint first, and vice versa.
        start_high_do: if True (default), start sweep with a high-DO setpoint (to more quickly equilibrate if
            environment is starting at atmospheric conditions). start_high_do=False produces a sequence that will
            equilibrate more quickly if the calibration environment already has low DO (e.g. if you just ran a sequence
            that put it at low DO)

    Returns:
        DataFrame of ordered setpoints. Each setpoint contains:
            o2_fraction: dissolved oxygen fraction based on and proportional to approximate mmHg targets
            temperature: temperature value (C)
            DO (approx mmHg): partial pressure of DO (approximate mmHg)
    """

    temperature_setpoints_low_to_high = np.linspace(
        min_temperature, max_temperature, temperatures_setpoint_count
    )
    temperature_setpoints = sorted(
        temperature_setpoints_low_to_high, reverse=start_high_temperature
    )

    do_setpoints = np.linspace(min_do_mmhg, max_do_mmhg, do_setpoint_count)

    # Every other temperature will have reversed DO setpoints to minimize equilibration time as we progress from one
    # temperature to the next. Set those up:
    do_setpoints_for_even_indexed_temperatures = sorted(
        do_setpoints, reverse=start_high_do
    )
    do_setpoints_for_odd_indexed_temperatures = sorted(
        do_setpoints, reverse=not start_high_do
    )

    setpoints = pd.DataFrame(
        [
            # fmt: off
            {
                "temperature": temperature,
                "DO (approx mmHg)": do
            }
            # fmt: on
            for temperature_index, temperature in enumerate(temperature_setpoints)
            # Every other temperature gets a reversed set of DO setpoints
            for do in (
                do_setpoints_for_even_indexed_temperatures
                if temperature_index % 2 == 0
                else do_setpoints_for_odd_indexed_temperatures
            )
        ]
    )

    # Calculate O2 fraction based on mmHg
    # We include both because the calibration program expects a fraction, but mmHg is a little nicer for humans
    setpoints["o2_fraction"] = (
        setpoints["DO (approx mmHg)"] / AVERAGE_SYSTEM_PRESSURE_MMHG
    )
    return setpoints


def remove_invalid_points(sweep, o2_source_gas_o2_fraction):
    """ Provide a copy of a sweep, limited to setpoints that can actually be hit with the calibration setup.
    If any setpoints are filtered out, we'll call logger.info so you know what they are. Note that this is expected
    for many calibration situations, as it's hard to predict what setpoints will be achievable with a given O2 source
    gas O2 fraction, flow rate and O2 percent flow rate.
    """
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
    start_high_temperature: bool = False,
    start_high_do: bool = True,
    flow_rate_slpm: float = DEFAULT_FLOW_RATE_SLPM,
) -> pd.DataFrame:
    """ Create a sweep of setpoints across a range of temperatures and oxygen levels
    Efficient ordering minimizes equilibration time. In our efficient setpoint ordering:
    * temperatures are in monotonically increasing or decreasing order (based on the start_high_temperature param)
    * DO also changes monotonically within each temperature.
        * when one temperature starts with high DO, the next temperature will start with low DO, and vice versa

    Args:
        min_temperature: lowest temperature setpoint to hit
        max_temperature: highest temperature setpoint to hit
        temperatures_setpoint_count: number of distinct temperatures to include
        min_do_mmhg: lowest DO value to hit (approximate mmHg)
        max_do_mmhg: highest DO value to hit (approximate mmHg)
             DO mmHg values are approximate because total pressure of the chamber may fluctuate, and we only actually
             control the percentage of oxygen present.
        do_setpoint_count: number of distinct DO values to include
        o2_source_gas_o2_fraction: fraction of oxygen in oxygen source gas for this run
        start_high_temperature: if True (default=False), hit the highest temperature setpoint first, and vice versa.
        start_high_do: if True (default), start sweep with a high-DO setpoint (to more quickly equilibrate if
            environment is starting at atmospheric conditions). start_high_do=False produces a sequence that will
            equilibrate more quickly if the calibration environment already has low DO (e.g. if you just ran a sequence
            that put it at low DO)
        flow_rate_slpm: flow rate to use in all setpoints (SLPM)

    Returns:
        pd.DataFrame of efficiently ordered setpoints with the following columns:
            temperature: The desired setpoint temperature in degrees Celsius.
            flow_rate_slpm: The desired setpoint flow rate in Standard Liters Per Minute
            o2_fraction: The desired O2 fraction of the output gas mix.
            DO (approx mmHg): approximate partial pressure of DO (directly proportional to o2_fraction, provided for
                human friendliness)
            hold_time: The amount of time in seconds to hold at this setpoint for data collection.
        Note that the returned setpoints are filtered to only those that can actually hit given the provided O2 source
        gas O2 fraction and flow rate.
    """
    raw_setpoints = generate_ordered_setpoints(
        min_temperature=min_temperature,
        max_temperature=max_temperature,
        temperatures_setpoint_count=temperatures_setpoint_count,
        min_do_mmhg=min_do_mmhg,
        max_do_mmhg=max_do_mmhg,
        do_setpoint_count=do_setpoint_count,
        start_high_do=start_high_do,
        start_high_temperature=start_high_temperature,
    )

    raw_setpoints["flow_rate_slpm"] = flow_rate_slpm
    raw_setpoints["hold_time"] = hold_time_seconds

    cleaned_setpoints = remove_invalid_points(
        raw_setpoints, o2_source_gas_o2_fraction=o2_source_gas_o2_fraction
    )

    return cleaned_setpoints
