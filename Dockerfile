FROM python:slim
RUN pip install slack_sdk boto3
WORKDIR /app
COPY . .
CMD ["/app/run.py"]
