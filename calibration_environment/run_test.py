import time
from unittest.mock import sentinel, call

import pytest
import pandas as pd

from .configure import CalibrationConfiguration
from . import run as module


@pytest.fixture
def mock_drivers(mocker):
    mocker.patch.object(module.gas_mixer, "start_constant_flow_mix_with_retry")
    mocker.patch.object(module.gas_mixer, "stop_flow_with_retry")
    mocker.patch.object(module.gas_mixer, "get_mixer_status_with_retry")
    mocker.patch.object(module.gas_mixer, "get_gas_ids_with_retry")

    mocker.patch.object(module.water_bath, "send_command_and_parse_response")
    mocker.patch.object(module.water_bath, "initialize")
    mocker.patch.object(module.water_bath, "send_settings_command_and_parse_response")


@pytest.fixture
def mock_get_all_sensor_data(mocker):
    return mocker.patch(
        "calibration_environment.data_logging.get_all_sensor_data",
        return_value=pd.Series(),
    )


@pytest.fixture
def mock_check_status(mocker):
    return mocker.patch.object(module, "check_status")


@pytest.fixture
def mock_wait_for_temperature_equilibration(mocker):
    return mocker.patch.object(module, "wait_for_temperature_equilibration")


@pytest.fixture
def mock_wait_for_do_equilibration(mocker):
    return mocker.patch.object(module, "wait_for_do_equilibration")


@pytest.fixture
def mock_wait_for_equilibration(
    mock_wait_for_temperature_equilibration, mock_wait_for_do_equilibration
):
    pass


@pytest.fixture
def mock_output_filepath(tmp_path):
    return tmp_path / "test.csv"


@pytest.fixture
def mock_shut_down(mocker):
    return mocker.patch.object(module, "_shut_down")


DEFAULT_SETPOINTS = pd.DataFrame(
    [{"temperature": 15, "flow_rate_slpm": 2.5, "o2_fraction": 50, "hold_time": 0.01}]
)


DEFAULT_CONFIGURATION = CalibrationConfiguration(
    setpoint_sequence_csv_filepath="experiment.csv",
    setpoints=DEFAULT_SETPOINTS,
    com_ports={"ysi": "COM11", "gas_mixer": "COM22", "water_bath": "COM21"},
    o2_source_gas_fraction=0.21,
    loop=False,
    output_csv_filepath="test.csv",
    collection_interval=0.01,
    cosmobot_experiment_name=None,
    cosmobot_hostname=None,
    cosmobot_exposure_time=None,
    capture_images=False,
)


@pytest.fixture
def mock_get_calibration_configuration(mocker, mock_output_filepath):
    mock_calibration_configuration = DEFAULT_CONFIGURATION._replace(
        output_csv_filepath=mock_output_filepath
    )
    return mocker.patch.object(
        module,
        "get_calibration_configuration",
        return_value=mock_calibration_configuration,
    )


@pytest.fixture
def mock_post_slack_message(mocker):
    return mocker.patch.object(module, "post_slack_message")


@pytest.fixture
def mock_all_integrations(
    mock_drivers,
    mock_get_all_sensor_data,
    mock_get_calibration_configuration,
    mock_check_status,
    mock_wait_for_equilibration,
    mock_shut_down,
    mock_post_slack_message,
):
    # This pytest fixture just combines all other fixtures into one so that our
    # test function signatures don't explode with repetitive mocks
    pass


class TestRunCalibration:
    def test_collects_data_at_configured_rate(
        self,
        mock_output_filepath,
        mock_get_calibration_configuration,
        mock_all_integrations,
    ):
        """
        Test is configured to hold at setpoint for 0.2 seconds, and read data
        every 0.09 seconds. 0.09 is used instead of 0.1 to allow some wiggle room.
        """
        setpoint_hold_time = 0.2
        data_collection_interval = 0.09

        setpoints = pd.DataFrame(
            [
                {
                    "temperature": 15,
                    "flow_rate_slpm": 2.5,
                    "o2_fraction": 50,
                    "hold_time": setpoint_hold_time,
                }
            ]
        )

        mock_get_calibration_configuration.return_value = DEFAULT_CONFIGURATION._replace(
            setpoints=setpoints,
            collection_interval=data_collection_interval,
            output_csv_filepath=mock_output_filepath,
        )

        module.run([])

        output_csv = pd.read_csv(mock_output_filepath)

        expected_output_rows = setpoint_hold_time // data_collection_interval
        assert len(output_csv) == expected_output_rows

    def test_correct_values_saved_to_csv(
        self, mock_all_integrations, mock_output_filepath, mock_get_all_sensor_data
    ):

        expected_csv = pd.DataFrame(
            [
                {
                    "equilibration status": "equilibrated",
                    "loop count": 0,
                    "o2 source gas fraction": 0.21,
                    "setpoint O2 fraction": 50.0,
                    "setpoint flow rate (SLPM)": 2.5,
                    "setpoint hold time seconds": 0.01,
                    "setpoint temperature (C)": 15.0,
                    "stub data": 1,
                }
            ]
        )

        mock_get_all_sensor_data.return_value = pd.Series({"data": 1}).add_prefix(
            "stub "
        )

        module.run([])

        output_csv = pd.read_csv(mock_output_filepath).drop(columns=["timestamp"])

        pd.testing.assert_frame_equal(expected_csv, output_csv)

    def test_checks_status(self, mock_all_integrations, mock_check_status):
        module.run([])

        mock_check_status.assert_called()

    def test_shuts_down_at_end(self, mock_all_integrations, mock_shut_down):
        module.run([])

        mock_shut_down.assert_called()

    def test_notifies_on_successful_end(
        self, mock_all_integrations, mock_post_slack_message
    ):
        module.run([])

        mock_post_slack_message.assert_has_calls(
            [
                call("Calibration routine ended successfully!"),
                call("Calibration system shut down."),
            ]
        )

    @pytest.mark.parametrize(
        "function_that_might_raise",
        [
            (module.gas_mixer, "start_constant_flow_mix_with_retry"),
            (module.water_bath, "send_command_and_parse_response"),
            (module.water_bath, "initialize"),
            (module, "collect_data_to_csv"),
        ],
    )
    def test_shuts_down_and_notifies_after_error(
        self,
        mocker,
        mock_all_integrations,
        mock_shut_down,
        mock_post_slack_message,
        function_that_might_raise,
    ):
        mocker.patch.object(*function_that_might_raise).side_effect = Exception(
            "Mock error"
        )

        # The expectation is that the system gets shut down, but the error is re-raised
        # so that it gets bubbled up
        with pytest.raises(Exception):
            module.run([])

        mock_shut_down.assert_called()
        mock_post_slack_message.assert_has_calls(
            [
                call(
                    "Calibration routine ended with error! Mock error",
                    mention_channel=True,
                ),
                call("Calibration system shut down."),
            ]
        )

    def test_shuts_down_and_notifies_after_keyboard_interrupt(
        self,
        mock_all_integrations,
        mock_wait_for_temperature_equilibration,
        mock_shut_down,
        mock_post_slack_message,
    ):
        # Pick an arbitrary function to have a KeyboardInterrput
        mock_wait_for_temperature_equilibration.side_effect = KeyboardInterrupt()

        # The expectation is that the system gets shut down, but the error is re-raised
        # so that it gets bubbled up
        with pytest.raises(KeyboardInterrupt):
            module.run([])

        mock_shut_down.assert_called()
        mock_post_slack_message.assert_has_calls(
            [
                call("Calibration routine ended by user."),
                call("Calibration system shut down."),
            ]
        )

    @pytest.mark.parametrize(
        "setpoint_temperatures,expected_wait_call_count",
        (
            ((15, 25), 4),  # called twice at each temperature setpoint change
            ((15, 15), 2),  # only called for initial temperature equilibration
        ),
    )
    def test_calls_wait_for_temperature_equilibration_only_if_temperature_changed(
        self,
        mock_all_integrations,
        mock_get_calibration_configuration,
        mock_output_filepath,
        mock_wait_for_temperature_equilibration,
        setpoint_temperatures,
        expected_wait_call_count,
    ):
        hold_time = 0.01
        collection_interval = hold_time  # collect one data point per setpoint
        setpoints = pd.DataFrame(
            [
                {
                    "temperature": setpoint_temperature,
                    "flow_rate_slpm": sentinel.flow_rate_slpm,
                    "o2_fraction": sentinel.o2_fraction,
                    "hold_time": hold_time,
                }
                for setpoint_temperature in setpoint_temperatures
            ]
        )

        mock_get_calibration_configuration.return_value = DEFAULT_CONFIGURATION._replace(
            setpoints=setpoints,
            output_csv_filepath=mock_output_filepath,
            collection_interval=collection_interval,
        )

        module.run([])

        assert (
            mock_wait_for_temperature_equilibration.call_count
            == expected_wait_call_count
        )


@pytest.fixture
def mock_gas_mixer_shutdown(mocker):
    return mocker.patch.object(module.gas_mixer, "stop_flow_with_retry")


@pytest.fixture
def mock_water_bath_shutdown(mocker):
    return mocker.patch.object(
        module.water_bath, "send_settings_command_and_parse_response"
    )


@pytest.fixture
def mock_time_sleep(mocker):
    # Mock time.sleep so that we don't have to wait 5 seconds on every test
    return mocker.patch.object(time, "sleep")


class TestShutDown:
    def test_shuts_down_gas_mixer_and_water_bath(
        self, mock_gas_mixer_shutdown, mock_water_bath_shutdown, mock_time_sleep
    ):

        module._shut_down(sentinel.gas_mixer_com_port, sentinel.water_bath_com_port)

        mock_gas_mixer_shutdown.assert_called()
        mock_water_bath_shutdown.assert_called()
        mock_time_sleep.assert_called_with(5)

    def test_shuts_down_water_bath_if_gas_mixer_raises(
        self, mock_gas_mixer_shutdown, mock_water_bath_shutdown, mock_time_sleep
    ):
        mock_gas_mixer_shutdown.side_effect = Exception()

        # The expectation is that the Exception is raised and bubbled up, but the code
        # in the finally block still gets called, so the water bath still gets shut down
        with pytest.raises(Exception):
            module._shut_down(sentinel.gas_mixer_com_port, sentinel.water_bath_com_port)

        mock_gas_mixer_shutdown.assert_called()
        mock_water_bath_shutdown.assert_called()
        mock_time_sleep.assert_called_with(5)
