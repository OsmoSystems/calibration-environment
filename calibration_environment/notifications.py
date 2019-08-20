import os

import slack


DEFAULT_SLACK_CHANNEL = "#water-bath-funtimes"


def post_slack_message(message: str, mention_channel: bool = False):
    """ Posts a message as the "Calibration Environment Bot" using the "CalibrationNotify" app
    (https://api.slack.com/apps/AMF4BTRM4)
    Pulls the slack API token from the SLACK_API_TOKEN environment variable.

    Args:
        message: The message contents
        mention_channel: whether to mention @channel in the message
    """
    client = slack.WebClient(token=os.environ["SLACK_API_TOKEN"])

    mention = "<!channel> " if mention_channel else ""

    response = client.chat_postMessage(
        channel=DEFAULT_SLACK_CHANNEL, text=f"{mention}{message}"
    )
    assert response["ok"]
