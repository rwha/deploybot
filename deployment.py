import datetime
import logging
from operator import itemgetter

from config import SLACK_CHANNEL

logger = logging.getLogger(__name__)


class Deployment:
    """Generate slack messages for code deployments."""

    divider = {"type": "divider"}

    status_icons = {
        "Created": ":large_blue_circle:",
        "Queued": ":large_blue_circle:",
        "Baking": ":large_blue_circle:",
        "Succeeded": ":heavy_check_mark:",
        "InProgress": ":large_blue_circle:",
        "Failed": ":X:",
        "Canceled": ":no_entry_sign:",
        "Stopped": ":no_entry_sign:",
        "Superseded": ":heavy_minus_sign:",
        "Started": ":large_blue_circle:",
        "Resumed": ":large_blue_circle:",
    }

    def __init__(self, deploymentId, client):
        self.channel = SLACK_CHANNEL
        self.username = "codedeploy"
        self.icon = ":code_deploy:"
        self.timestamp = ""
        self.deploymentId = deploymentId
        self.client = client

        try:
            self.deploymentInfo = self.client.get_deployment(
                deploymentId=self.deploymentId
            ).get("deploymentInfo", {})
        except Exception as e:
            logger.warning("unable to get deployment info", repr(e))
            self.deploymentInfo = {}

        self.application = self.deploymentInfo.get("applicationName")
        self.is_rollback = bool(
            self.deploymentInfo.get("creator") == "codeDeployRollback"
        )
        if self.is_rollback:
            self.application = f"[ROLLBACK] {self.application}"
        self.started = self.deploymentInfo.get(
            "startTime", self.deploymentInfo.get("createTime")
        )
        self.completed = self.deploymentInfo.get("completeTime", False)
        self.status = self.deploymentInfo.get("status")
        self.description = self.deploymentInfo.get("description", None)
        self.overview = self.deploymentInfo.get("deploymentOverview", {})
        self.targets = {}

    def __repr__(self):
        return f"Deployment(deploymentId='{self.deploymentId}')"

    def get_msg(self):
        self.refresh_info()
        return {
            "text": f"deployment: {self.application}",
            "ts": self.timestamp,
            "channel": self.channel,
            "username": self.username,
            "icon_emoji": self.icon,
            "blocks": [
                self.get_status(),
                self.get_description(),
                self.get_result(),
                self.divider,
                self.get_target_status(),
            ],
        }

    def _get_target_ids(self):
        if self.targets:
            return list(self.targets.keys())
        try:
            response = self.client.list_deployment_targets(deploymentId=self.deploymentId)
            return response.get("targetIds", [])
        except Exception as e:
            logger.warning("unable to get deployment targets")
            return []

    def _get_target_data(self):
        target_ids = self._get_target_ids()
        if not target_ids:
            return []
        try:
            response = self.client.batch_get_deployment_targets(
                deploymentId=self.deploymentId, targetIds=target_ids
            )
            resp_targets = response.get("deploymentTargets", [])
            targets = []
            for target in resp_targets:
                _type = target.get("deploymentTargetType")
                target_type = f"{_type[0].lower()}{_type[1:]}"
                targets.append(target.get(target_type))
            return targets
        except Exception as e:
            logger.warning("unable to get deployment target data", repr(e))
            return []

    def _get_icon(self, status=None):
        if status is None:
            status = self.status
        return self.status_icons.get(status, ":grey_question:")

    def _get_deploy_stats(self):
        if not self.overview:
            return "pending..."

        if self.status == "Succeeded" and self.finished:
            ttl = (self.completed - self.started).seconds
            logger.info(f"deployment {self.deploymentId} completed in {ttl} seconds")
            mins, secs = divmod(ttl, 60)
            minstr = f"{mins} min " if mins > 0 else ""
            secstr = f"{secs} sec" if secs > 0 else ""
            return f"Deployed to {len(self.targets)} in {minstr}{secstr}"

        # ex: "InProgress: 1 | Pending: 2 | Succeeded: 1"
        return " | ".join(f"{k}: {v}" for k, v in sorted(self.overview.items()) if v > 0)

    def refresh_info(self):
        try:
            response = self.client.get_deployment(deploymentId=self.deploymentId)
            info = response.get("deploymentInfo", None)
        except Exception as e:
            logger.warning("unable to get deployment info", repr(e))
            info = None
        if info is not None:
            self.deploymentInfo = info
            self.completed = info.get("completeTime", False)
            self.status = info.get("status")
            self.overview = info.get("deploymentOverview", {})

        for target_info in self._get_target_data():
            target_id = target_info.get("targetId", None)
            if target_id is None:
                continue
            if target_id not in self.targets:
                self.targets[target_id] = DeploymentTarget(target_info)
            else:
                self.targets[target_id].update(target_info)

    def get_status(self):
        icon = self._get_icon()
        if not self.deploymentInfo:
            return self._get_block(f"{icon}  Waiting for deployment info...")
        return self._get_block(f"{icon}  {self.application} - {self.status}")

    def get_description(self):
        if self.description:
            return self._get_block(f"{self.description}")
        return self.divider

    def get_result(self):
        if not self.deploymentInfo:
            return self._get_block("pending...")
        return self._get_block(self._get_deploy_stats())

    def get_target_status(self):
        lines = [t.status for t in self.targets.values()]
        if not lines:
            return self._get_block("No installation targets available.")
        target_lines = "\n".join(lines)
        return self._get_block(f"```{target_lines}```")

    @property
    def finished(self):
        done_statuses = {"Succeeded", "Failed", "Stopped", "Superseded", "Canceled"}
        return self.completed and self.status in done_statuses

    @staticmethod
    def _get_block(text):
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


class DeploymentTarget:
    def __init__(self, target_info):
        self.target_info = target_info
        self.target_id = target_info.get("targetId")
        self._status = target_info.get("status")
        self.lifecycle_events = {}
        self.process_lifecycle_events()

    def __repr__(self):
        return f"DeploymentTarget(target_id='{self.target_id}')"

    def process_lifecycle_events(self):
        events = self.target_info.get("lifecycleEvents", [])
        if not events:
            return

        for event in events:
            name = event.get("lifecycleEventName")
            status = event.get("status", "")
            if status == "Failed":
                logger.warning(f"failure event in deployment target {self.target_id}")
                logger.warning(str(event))
                diagnostics = event.get("diagnostics", {})
                errorcode = diagnostics.get("errorCode", "unknown error")
                message = diagnostics.get("message", "cause unavailable")
                status += f": {errorcode} - {message}"
            self.lifecycle_events[name] = status

    def get_current_activity(self):
        if self._status in {"Succeeded", "Pending"}:
            return self._status

        # unknown final status
        single = set(self.lifecycle_events.values())
        if len(single) == 1:
            return single.pop()

        # if we get here, it's in progress. find and return the name.
        for name, status in self.lifecycle_events.items():
            # most likely the first InProgress event is the right one
            if status == "InProgress":
                return f" {name}"
            if "Failed" in status:
                return f" {name}: `{status}`"

        # try last completed event
        events = [e for e in self.target_info.get("lifecycleEvents", [])
                  if "endTime" in e]
        if events:
            last_finished = max(events, key=itemgetter("endTime"))
            return last_finished["lifecycleEventName"]

        # last resort is the target status
        return self._status

    def update(self, target_info):
        self.target_info = target_info
        self._status = target_info.get("status")
        self.process_lifecycle_events()

    @property
    def status(self):
        return f"{self.target_id}:  {self.get_current_activity()}"

