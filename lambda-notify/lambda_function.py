import json
import os
import urllib.parse
from datetime import datetime, timezone, timedelta

import boto3

s3 = boto3.client("s3")
sns = boto3.client("sns")
TOPIC_ARN = os.environ["TOPIC_ARN"]
IST = timezone(timedelta(hours=5, minutes=30))

def lambda_handler(event, context):
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

    # Skip companion metadata files
    if key.endswith(".json"):
        return

    size_kb = round(record["s3"]["object"]["size"] / 1024)
    uploaded_at = datetime.fromisoformat(record["eventTime"].replace("Z", "+00:00")) \
                          .astimezone(IST).strftime("%d/%m/%Y, %I:%M:%S %p")

    # Read companion JSON for metadata
    try:
        meta_obj = s3.get_object(Bucket=bucket, Key=key + ".json")
        meta = json.loads(meta_obj["Body"].read())
    except Exception:
        meta = {}

    name = meta.get("name", "Unknown")
    email = meta.get("email", "Not provided")
    consent = "Yes" if meta.get("consent") == "true" else "No"

    message = f"""New Testimonial Received!

Name:      {name}
Email:     {email}
Consent:   {consent}
Uploaded:  {uploaded_at} IST
File:      {key}
Size:      {size_kb} KB

View in S3 Console:
https://s3.console.aws.amazon.com/s3/object/{bucket}?prefix={key}"""

    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=f"New Testimonial from {name}",
        Message=message,
    )
