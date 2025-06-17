from pathlib import Path

from slack_sdk import WebClient


def upload_to_slack(filepath: Path, slack_client: WebClient, channel: str, text: str = ''):
    return slack_client.files_upload_v2(channel=channel, file=filepath, initial_comment=text)
