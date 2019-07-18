[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

# calibration-environment

Automation and data collection tools for the Osmo calibration environment

# Installation
Install the repo using `pip` to ensure dependencies are available and to create
the shortcut command to run the automation program.

```sh
pip install git+ssh://git@github.com/osmosystems/calibration-environment.git@[CHANGESET]
```

# Usage

Run the automation program using the command line entrypoint:
```sh
run_calibration --setpoint-sequence-filepath setpoints.csv --o2-source-fraction 0.21 --collection-interval 300
```

Use `run_calibration --help` for a full list of options.

## Setpoint CSV file schema
| Heading                | Description                                                                 |
| ---------------------- | --------------------------------------------------------------------------- |
| temperature            | The desired setpoint temperature in degrees Celsius.                                           |
| flow_rate_slpm         | The desired setpoint flow rate in Standard Liters Per Minute                                             |
| o2_target_gas_fraction | The desired O2 fraction of the output gas mix.                                         |
| hold_time              | The amount of time in seconds to hold at this setpoint for data collection. |