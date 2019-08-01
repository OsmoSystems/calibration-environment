def estimate_number_images_collected(sweep, cosmobot_data_collection_interval_seconds):
    """
    Args:
        sweep: a dataframe of setpoints.
        cosmobot_data_collection_interval_seconds: How frequently data will be sampled in the calibration environment
            and on cosmobot, in seconds
    """
    return sweep["hold_time"].sum() / cosmobot_data_collection_interval_seconds
