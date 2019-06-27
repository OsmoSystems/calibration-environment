import pandas as pd

import serial


ALICAT_BAUD_RATE = 19200


def send_serial_command_and_get_response(command_str, port, approx_return_length=200):
    """ Given a serial command, send it on a serial port and return the response.
    """
    # Add the expected line ending and convert to bytes for serial transmission
    command_bytes = bytes("{}\r".format(command_str), encoding="utf8")

    with serial.Serial(
        port, ALICAT_BAUD_RATE, timeout=approx_return_length / ALICAT_BAUD_RATE + 0.05
    ) as connection:
        connection.write(command_bytes)
        return_value_with_line_ending = connection.readline()

    if return_value_with_line_ending:
        return return_value_with_line_ending[:-1].decode("utf8")

    return return_value_with_line_ending.decode("utf8")


_MIXER_STATUS_RESPONSE_FIELDS = [
    "deviceID",
    "version",
    "mixStatus",
    "mixAlarm",
    "pressureUnits",
    "flowUnits",
    "volumeUnits",
    "numPorts",
    "mixAlarmEnable",
    "gasAnalyzerAlarmEnable",
    "mixPressure",
    "mixFlow",
    "mixVolume",
    "gasAnalyzer",
    "status1",
    "pressure1",
    "flow1",
    "totalVolume1",
    "totalFraction1",
    "status2",
    "pressure2",
    "flow2",
    "totalVolume2",
    "totalFraction2",
]

_LOW_FEED_PRESSURE_ALARM_BIT = 0x008000
_ONE_BILLION = 1000000000


def _has_low_feed_pressure(alarm_str):
    """ Given an alarm string from a mixer status, indicate whether low feed pressure is present
    """
    return bool(int(alarm_str) & _LOW_FEED_PRESSURE_ALARM_BIT)


def _ppb_to_fraction(ppb_str):
    return int(ppb_str) / _ONE_BILLION


def _fraction_to_ppb(fraction):
    return str(int(fraction * _ONE_BILLION))


# TODO: check that pressure units are correct


def _parse_mixer_status(mixer_status_str):
    mixer_status_values = mixer_status_str.split()
    mixer_status_dict = dict(zip(_MIXER_STATUS_RESPONSE_FIELDS, mixer_status_values))
    return pd.Series(
        {
            "flow rate (SLPM)": float(mixer_status_dict["mixFlow"]),
            "mix pressure (mmHg)": float(mixer_status_dict["mixPressure"]),
            "low feed pressure alarm": _has_low_feed_pressure(
                mixer_status_dict["mixAlarm"]
            ),
            "low feed pressure alarm - N2": _has_low_feed_pressure(
                mixer_status_dict["status1"]
            ),
            "low feed pressure alarm - O2 source gas": _has_low_feed_pressure(
                mixer_status_dict["status2"]
            ),
            "N2 fraction in mix": _ppb_to_fraction(mixer_status_dict["totalFraction1"]),
            "O2 source gas fraction in mix": _ppb_to_fraction(
                mixer_status_dict["totalFraction2"]
            ),
        }
    )


def get_mixer_status(port):
    command = "A QMXS"
    response = send_serial_command_and_get_response(command, port)
    return _parse_mixer_status(response)


def set_flow_rate_and_gas_mix(port, flow_rate_slpm, o2_source_gas_fraction):
    n2_fraction = 1 - o2_source_gas_fraction
    n2_ppb = _fraction_to_ppb(n2_fraction)
    o2_source_gas_ppb = _fraction_to_ppb(o2_source_gas_fraction)

    commands_and_expected_responses = [
        (f"A MXRM 3", "A 3"),  # Set mixer mode to constant flow
        (  # Set desired flow rate
            f"A MXRFF {flow_rate_slpm}",
            f"A {flow_rate_slpm:.2f} 7 SLPM",
        ),
        (  # Set target fraction
            f"A MXMF {n2_ppb}, {o2_source_gas_ppb}",
            f"A {n2_ppb} {o2_source_gas_ppb}",
        ),
        (f"A MXRS 1", "A 2"),  # Start mixin'
    ]

    for command, expected_response in commands_and_expected_responses:
        response = send_serial_command_and_get_response(command, port)
        assert response == expected_response, (response, expected_response)


def stop_flow(port):
    command = "A MXRS 2"
    response = send_serial_command_and_get_response(command, port)
    assert response == "A 3", response  # Mixer stopped, ready to start
