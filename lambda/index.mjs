import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const s3 = new S3Client({});
const BUCKET = process.env.BUCKET_NAME;

export const handler = async (event) => {
  const { name, email, filename, contentType, consent } = JSON.parse(event.body || "{}");

  if (!name || !filename || !contentType) {
    return { statusCode: 400, body: JSON.stringify({ error: "name, filename, and contentType are required" }) };
  }

  const key = `testimonials/${Date.now()}-${filename}`;

  const command = new PutObjectCommand({
    Bucket: BUCKET,
    Key: key,
    ContentType: contentType,
    Metadata: {
      name,
      ...(email && { email }),
      consent: consent || "true",
    },
  });

  const url = await getSignedUrl(s3, command, { expiresIn: 300 });

  return {
    statusCode: 200,
    headers: { "Access-Control-Allow-Origin": "*" },
    body: JSON.stringify({ url, key }),
  };
};
