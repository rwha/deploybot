import os


AWS_REGION = os.environ.get("AWS_REGION", "CI_AWS_REGION")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "CI_SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "CI_SLACK_CHANNEL")
