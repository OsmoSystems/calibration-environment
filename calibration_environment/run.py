# Some mapping between output data column names, and functions to call to fetch them
# Will live somewhere else
sensors_configuration = {
    "sensor_temperature": read_temperature_sensor,
    "sensor_pressure": read_pressure_sensor,
}


def run(cli_args):
    # Parse the configuration parameters from cli args
    calibration_configuration = get_calibration_configuration(cli_args)

    output_column_names = [
        "setpoint_temperature",
        "setpoint_gas_mix",
        "timestamp",
        # Maybe also an experiment name / sweep # or other group id
    ].append(sensors_configuration.keys())

    # Initialize the data and output csv file so it can be `tail`ed
    collected_data = pd.DataFrame(columns=output_column_names)
    collected_data.to_csv(calibration_configuration["output_csv"], index=False)

    while True:
        for setpoint in calibration_configuration["setpoints"]:
            # Set the gax mixer ratio -- still not totally sure on what
            # the user is inputting, and what the mfc interface is being sent
            mfc.set_gas_mix(setpoint["mfc"], calibration_configuration["mfc2_gas_pct"])
            # Set the water bath temperature
            water_bath.set_temperature(setpoint["temperature"])

            # Magical function that returns when the system is ready, or has an error
            error = wait_for_equilibration()

            if error is not None:
                # Print the error, or wait for input, or perform cleanup and exit
                pass

            for i in range(calibration_configuration["read_count"]):
                # Set up a data frame to collect data into
                row = pd.Series(index=output_column_names)
                row["setpoint_temperature"] = setpoint["temperature"]
                row["setpoint_gas_mix"] = setpoint["mfc"]
                row["timestamp"] = datetime.now()

                try:
                    # Read from each sensor and add to the dataframe
                    for sensor_name, sensor_read_caller in sensors_configuration:
                        value = sensor_read_caller()
                        row[sensor_name] = value
                except e:
                    # Handling here might depend on the error?
                    pass

                # Append the row to the rest of the data
                collected_data.loc[collected_data.shape[0]] = row
                # Use `None` as file to return the string value
                serialized_values = collected_data.iloc[-1].to_csv(
                    None, index=False, header=False
                )

                # Append the csv row to the output file
                with open(calibration_configuration["output_csv"], "w+") as log:
                    log.write(serialized_values)

                # Don't wait to collect the next data point
                # if we're done collecting at this setpoint
                if i + 1 != calibration_configuration["read_count"]:
                    # Wait to collect the next data point
                    time.sleep(calibration_configuration["read_interval"])

        # Not a hard requirement to configurably loop forever
        if not calibration_configuration["loop"]:
            return
