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


def _generate_run_experiment_command(experiment_name, duration):
    run_experiment_path = "/home/pi/.local/bin/run_experiment"
    variant_params = "--exposure-time 0.8 -ISO 100 --led-on"
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

    run_experiment_command = _generate_run_experiment_command(experiment_name, duration)

    logger.info(
        f"Starting image capture on cosmobot.\nCommand: {run_experiment_command}"
    )

    return ExperimentStreams(*ssh_client.exec_command(run_experiment_command))


class BadExitStatus(Exception):
    def __init__(self, exit_status):
        super().__init__(
            f"Received bad exit status ({exit_status}) from run_experiment on cosmobot"
        )


def wait_for_exit(experiment_streams: ExperimentStreams) -> None:
    stdout = experiment_streams.stdout
    exit_status = stdout.channel.recv_exit_status()

    if exit_status != 0:
        # TODO raise different error for -1 vs. >0? not sure why we would ever receive -1 (maybe lost connection)
        raise BadExitStatus(exit_status)


# TODO delete this function if we don't use it
def ensure_no_bad_exit(experiment_streams: ExperimentStreams) -> None:
    # raise an exception if there was a bad exit on the experiment
    stdout = experiment_streams.stdout
    if stdout.channel.exit_status_ready():
        exit_status = stdout.channel.recv_exit_status()

    if exit_status != 0:
        # TODO raise different error for -1 vs. >0?
        raise BadExitStatus(exit_status)
