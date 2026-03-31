import { S3Client, HeadObjectCommand } from "@aws-sdk/client-s3";
import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";

const s3 = new S3Client({});
const sns = new SNSClient({});
const TOPIC_ARN = process.env.TOPIC_ARN;

export const handler = async (event) => {
  const record = event.Records[0];
  const bucket = record.s3.bucket.name;
  const key = decodeURIComponent(record.s3.object.key.replace(/\+/g, " "));
  const sizeKB = Math.round(record.s3.object.size / 1024);
  const uploadedAt = new Date(record.eventTime).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

  const { Metadata } = await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));

  const name = Metadata?.name || "Unknown";
  const email = Metadata?.email || "Not provided";
  const consent = Metadata?.consent === "true" ? "Yes" : "No";

  const message = `New Testimonial Received!

Name:      ${name}
Email:     ${email}
Consent:   ${consent}
Uploaded:  ${uploadedAt} IST
File:      ${key}
Size:      ${sizeKB} KB

View in S3 Console:
https://s3.console.aws.amazon.com/s3/object/${bucket}?prefix=${key}`;

  await sns.send(new PublishCommand({
    TopicArn: TOPIC_ARN,
    Subject: `New Testimonial from ${name}`,
    Message: message,
  }));
};
