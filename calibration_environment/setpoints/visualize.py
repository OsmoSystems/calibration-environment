from copy import copy

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

    return px.line(
        setpoints,
        title=title,
        x="DO (mmHg)",
        y="temperature",
        range_x=[0, OXYGEN_FRACTION_IN_ATMOSPHERE * ATMOSPHERIC_PRESURE_MMHG * 1.1],
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
    setpoints_sequences_copies = {
        name: copy(sequence) for name, sequence in setpoints_sequences.items()
    }

    for name, sequence_copy in setpoints_sequences_copies.items():
        sequence_copy["sequence_name"] = name
        sequence_copy["setpoint order"] = sequence_copy.index

    all_setpoints = pd.concat(setpoints_sequences_copies.values(), sort=False)

    return visualize_setpoints_sequence(
        all_setpoints, title, line_group="sequence_name", color="sequence_name"
    )
