import pandas as pd
from plotly import express as px

from calibration_environment.constants import (
    OXYGEN_FRACTION_IN_ATMOSPHERE,
    ATMOSPHERIC_PRESURE_MMHG,
)


def visualize_setpoints_sequence(setpoints, title, **line_kwargs):
    if "setpoint order" in setpoints.columns:
        # If the setpoints have been explicitly ordered, indicate that.
        mode = "lines+markers+text"
        text = "setpoint order"
    else:
        mode = "lines+markers"
        text = None  # type: ignore

    x_axis_upper_padding = 1.1

    return px.line(
        setpoints,
        title=title,
        x="DO (approx mmHg)",
        y="temperature",
        range_x=[
            0,
            OXYGEN_FRACTION_IN_ATMOSPHERE
            * ATMOSPHERIC_PRESURE_MMHG
            * x_axis_upper_padding,
        ],
        text=text,
        **line_kwargs
    ).update_traces(
        # Include text, markers and opacity in an attempt to make it clear where the
        # setpoints are and when there are multiple on top of one another
        mode=mode,
        marker=dict(size=10, opacity=0.5),
        textposition="top center",
    )


def visualize_multiple_setpoints_sequences(setpoints_sequences, title):
    all_setpoints = pd.concat(
        [
            sequence.assign(**{"sequence": name, "setpoint order": sequence.index})
            for name, sequence in setpoints_sequences.items()
        ],
        sort=False,
    )

    return visualize_setpoints_sequence(
        all_setpoints, title, line_group="sequence", color="sequence"
    )
