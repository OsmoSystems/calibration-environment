def estimate_number_images_collected(  # noqa e302 # pycodestyle bug https://github.com/PyCQA/pycodestyle/issues/860
    setpoints, cosmobot_data_collection_interval_seconds
):
    """
    Args:
        setpoints: a dataframe of setpoints.
        cosmobot_data_collection_interval_seconds: How frequently data will be sampled in the calibration environment
            and on cosmobot, in seconds
    """
    return setpoints["hold_time"].sum() / cosmobot_data_collection_interval_seconds
