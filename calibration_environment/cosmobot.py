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
    logger.info(f"Establishing SSH connection to cosmobot {cosmobot_hostname}...")

    cosmobot_username = "pi"

    client = paramiko.client.SSHClient()
    client.load_system_host_keys()
    client.connect(cosmobot_hostname, username=cosmobot_username)

    logger.info(f"Established SSH connection to cosmobot {cosmobot_hostname}")

    return client


def _generate_run_experiment_command(experiment_name, duration, exposure_time):
    run_experiment_path = "/home/pi/.local/bin/run_experiment"
    exposure_time_arg = (
        f" --exposure-time {exposure_time}" if exposure_time is not None else ""
    )
    variant_params = f"-ISO 100 --led-on{exposure_time_arg}"
    run_experiment_command = (
        f"{run_experiment_path} --name {experiment_name} --group-results --skip-temperature --interval 9"
        f' --duration {duration} --variant "{variant_params}"'
    )

    return run_experiment_command


ExperimentStreams = namedtuple("ExperimentStreams", ["stdin", "stdout", "stderr"])


def run_experiment(
    ssh_client: paramiko.client.SSHClient,
    experiment_name: str,
    duration: int,
    exposure_time: float = None,
) -> ExperimentStreams:
    """Run run_experiment (image capture program) on the cosmobot with the given name and duration

    Args:
        experiment_name: experiment name to pass to run_experiment
        duration: duration to pass to run_experiment

    Returns: ExperimentStreams object
    """

    run_experiment_command = _generate_run_experiment_command(
        experiment_name, duration, exposure_time
    )

    hostname = ssh_client.get_transport().hostname
    logger.info(
        f"Starting image capture on cosmobot {hostname}\n"
        f"Command: {run_experiment_command}"
    )

    return ExperimentStreams(*ssh_client.exec_command(run_experiment_command))


class BadExitStatus(Exception):
    def __init__(self, exit_status, hostname):
        super().__init__(
            f"Received bad exit status ({exit_status}) from run_experiment on cosmobot {hostname}"
        )


class ExitStatusNotReceived(Exception):
    def __init__(self, hostname):
        super().__init__(
            f"Could not read an exit status for run_experiment on cosmobot {hostname}"
        )


def _get_hostname_from_stream(stream):
    return stream.channel.get_transport().hostname


def wait_for_exit(experiment_streams: ExperimentStreams) -> None:
    stdout = experiment_streams.stdout
    exit_status = stdout.channel.recv_exit_status()

    hostname = _get_hostname_from_stream(stdout)
    if exit_status > 0:
        raise BadExitStatus(exit_status, hostname)
    elif exit_status == -1:
        # paramiko returns -1 if no exit status is provided by the server (connection issue?)
        raise ExitStatusNotReceived(hostname)


def attempt_to_close_connection(ssh_client: paramiko.client.SSHClient):
    """Call ssh_client.close() and log exception and cosmobot hostname if it fails"""

    # get hostname up here in case the transport isn't available after a failed close()
    hostname = ssh_client.get_transport().hostname

    try:
        ssh_client.close()
    except Exception as e:
        logging.error(
            f"exception occured while trying to close ssh connection to cosmobot {hostname}"
        )
        logging.exception(e)
