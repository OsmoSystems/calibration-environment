from unittest.mock import Mock

import pytest

from . import cosmobot as module


class TestGenerateRunExperimentCommand:
    def test_generates_expected_command(self):
        actual_command = module._generate_run_experiment_command(
            experiment_name="experiment_name", duration="90"
        )
        expected_command = (
            f"/home/pi/.local/bin/run_experiment --name experiment_name --group-results"
            f' --skip-temperature --interval 9 --duration 90 --variant "-ss 800000 -ISO 100 --led-on"'
        )

        assert actual_command == expected_command


class TestWaitForExit:
    def test_happy_path(self):
        mock_channel = Mock(recv_exit_status=Mock(return_value=0))
        mock_experiment_streams = Mock(stdout=Mock(channel=mock_channel))
        module.wait_for_exit(mock_experiment_streams)

    def test_raises_on_non_zero_exit_status(self):
        mock_channel = Mock(recv_exit_status=Mock(return_value=1))
        mock_experiment_streams = Mock(stdout=Mock(channel=mock_channel))
        with pytest.raises(module.BadExitStatus):
            module.wait_for_exit(mock_experiment_streams)
