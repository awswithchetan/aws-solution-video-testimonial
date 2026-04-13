import json
import os
import time
import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    filename = body.get("filename", "").strip()
    content_type = body.get("contentType", "").strip()
    consent = body.get("consent", "true")

    if not name or not filename or not content_type:
        return {"statusCode": 400, "body": json.dumps({"error": "name, filename, and contentType are required"})}

    key = f"testimonials/{int(time.time() * 1000)}-{filename}"

    # Store metadata as a companion JSON file (avoids metadata headers in presigned URL signature)
    meta = {"name": name, "consent": consent, "video": key}
    if email:
        meta["email"] = email
    s3.put_object(
        Bucket=BUCKET,
        Key=key + ".json",
        Body=json.dumps(meta),
        ContentType="application/json",
    )

    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"url": url, "key": key}),
    }
