## Slack messages for AWS CodeDeploy deployments

Sends and updates slack messages with detailed status for recent and active deployments.

_This has only been tested with deployments to EC2 instance targets._

### Required environment variables

 - `AWS_REGION` - e.g., "us-east-2"
 - `SLACK_BOT_TOKEN` - Slack bot token with chat:write, chat:write.customize, and chat:write.public scopes.
 - `SLACK_CHANNEL` - Where to send the messages.

### Running locally

```shell
AWS_REGION="us-east-2" SLACK_BOT_TOKEN="xoxb-asdf0978" SLACK_CHANNEL="#deployments" ./run.py
```

### Running in docker

```shell
docker build -t deploybot .
docker run -d -e AWS_REGION="us-east-1" -e SLACK_BOT_TOKEN="xoxb-asdf0987" -e SLACK_CHANNEL="#deployments" deploybot:latest
```

or

```shell
sed -i -e 's/CI_AWS_REGION/us-west-2/' -e 's/CI_SLACK_BOT_TOKEN/xoxb-asdf0987/' -e 's/CI_SLACK_CHANNEL/#deployments/' config.py
docker build -t deploybot .
docker run -d deploybot:latest
```

### Required AWS permissions

codedeploy:GetDeployment

codedeploy:ListDeployments

codedeploy:BatchGetDeploymentTargets

codedeploy:ListDeploymentTargets


Example policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "read0",
            "Effect": "Allow",
            "Action": [
                "codedeploy:GetDeployment",
                "codedeploy:ListDeployments"
            ],
            "Resource": "arn:aws:codedeploy:*:ACCOUNT:deploymentgroup:*/*"
        },
        {
            "Sid": "list0",
            "Effect": "Allow",
            "Action": [
                "codedeploy:BatchGetDeploymentTargets",
                "codedeploy:ListDeploymentTargets"
            ],
            "Resource": "*"
        }
    ]
}
```

### Misc

The `Deployment` class uses the `:code_deploy:` emoji for an icon. This can be added to Slack using codedeploy.png (included in this repo).
