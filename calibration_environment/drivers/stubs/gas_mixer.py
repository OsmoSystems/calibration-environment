import pandas as pd


def get_mixer_status(com_port):
    return pd.Series()


def get_gas_ids(com_port):
    return pd.Series()


def start_constant_flow_mix(
    com_port, flow_rate_slpm, target_o2_fraction, o2_set_point_fraction
):
    pass


def stop_flow(com_port):
    pass
