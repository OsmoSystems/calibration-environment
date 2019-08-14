from collections import namedtuple
import logging

import paramiko

logger = logging.getLogger(__name__)


def get_ssh_client(cosmobot_hostname: str) -> paramiko.client.SSHClient:
    """
    Get an SSHClient that is connected to the cosmobot.

    Args:
        cosmobot_hostname: hostname or ip address of the cosmobot

    Returns: paramiko SSHClient object
    """
    logger.info("Establishing SSH connection to cosmobot...")

    cosmobot_username = "pi"

    client = paramiko.client.SSHClient()
    client.load_system_host_keys()
    client.connect(cosmobot_hostname, username=cosmobot_username)

    logger.info("Cosmobot SSH connection established")

    return client


def _get_experiment_command(experiment_name, duration):
    run_experiment_path = "/home/pi/.local/bin/run_experiment"
    variant_params = "-ss 800000 -ISO 100 --led-on"
    run_experiment_command = (
        f"{run_experiment_path} --name {experiment_name} --group-results --skip-temperature --interval 9"
        f' --duration {duration} --variant "{variant_params}"'
    )

    return run_experiment_command


ExperimentStreams = namedtuple("ExperimentStreams", ["stdin", "stdout", "stderr"])


def run_experiment(
    ssh_client: paramiko.client.SSHClient, experiment_name: str, duration: int
) -> ExperimentStreams:
    """Run run_experiment (image capture program) on the cosmobot with the given name and duration

    Args:
        experiment_name: experiment name to pass to run_experiment
        duration: duration to pass to run_experiment

    Returns: ExperimentStreams object
    """

    run_experiment_command = _get_experiment_command(experiment_name, duration)

    logger.info(
        f"Starting image capture on cosmobot.\nCommand: {run_experiment_command}"
    )

    return ExperimentStreams(*ssh_client.exec_command(run_experiment_command))
