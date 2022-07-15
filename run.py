#!/usr//bin/env python
from datetime import datetime, timedelta, timezone
import logging
import time

import boto3
import slack_sdk

import config
from deployment import Deployment


active = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def send_message(slack_client, deployment_id, aws_client):
    response = None
    if deployment_id not in active:
        active[deployment_id] = Deployment(deployment_id, client=aws_client)
        logger.info(
            f"new deployment {deployment_id} for {active[deployment_id].application}"
        )
        msg = active[deployment_id].get_msg()
        try:
            response = slack_client.chat_postMessage(**msg)
        except Exception as exc:
            logger.critical(
                f"failed to send message for deployment {deployment_id}: {repr(exc)}"
            )
    else:
        msg = active[deployment_id].get_msg()
        try:
            response = slack_client.chat_update(**msg)
        except Exception as exc:
            logger.warning(
                f"failed to send updated message for deployment {deployment_id}: {repr(exc)}"
            )
    if response is not None:
        active[deployment_id].channel = response["channel"]
        active[deployment_id].timestamp = response["ts"]


def run_loop():
    slack_client = slack_sdk.web.WebClient(config.SLACK_BOT_TOKEN)
    aws_client = boto3.client("codedeploy", config.AWS_REGION)

    while True:
        now = datetime.now(tz=timezone(timedelta(hours=0), "UTC"))
        response = aws_client.list_deployments(
            createTimeRange={"end": now, "start": now - timedelta(hours=1)},
        )
        deployments = response.get("deployments")

        if not deployments and len(active) == 0:
            time.sleep(30)
            continue

        for deployment_id in deployments:
            if (deployment_id not in active) or (not active[deployment_id].finished):
                send_message(slack_client, deployment_id, aws_client)

        # clean up old deployments
        for x in list(active.keys()):
            if x not in deployments and active[x].finished:
                del active[x]

        if all(d.finished for d in active.values()):
            time.sleep(30)
        else:
            time.sleep(3)


if __name__ == "__main__":
    run_loop()
