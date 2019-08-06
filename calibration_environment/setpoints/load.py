import pandas as pd


def read_setpoint_sequence_file(sequence_csv_filepath: str) -> pd.DataFrame:
    setpoints = pd.read_csv(sequence_csv_filepath)
    return setpoints
