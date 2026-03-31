# Video Testimonial App — AWS Setup Guide

## 1. Create the S3 Bucket

```bash
aws s3api create-bucket --bucket your-testimonials-bucket --region us-east-1
```

### Enable static website hosting (for the frontend)
```bash
aws s3 website s3://your-testimonials-bucket/ --index-document index.html
```

### Set CORS on the bucket (required for browser uploads)
```bash
aws s3api put-bucket-cors --bucket your-testimonials-bucket --cors-configuration file://s3-cors.json
```

`s3-cors.json`:
```json
{
  "CORSRules": [{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["PUT", "GET"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }]
}
```

---

## 2. Deploy the Lambda Function

### Package it
```bash
cd lambda
npm install @aws-sdk/client-s3 @aws-sdk/s3-request-presigner
zip -r function.zip .
```

### Create IAM role for Lambda
```bash
aws iam create-role \
  --role-name testimonial-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name testimonial-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Allow Lambda to put objects in S3
aws iam put-role-policy \
  --role-name testimonial-lambda-role \
  --policy-name s3-put-policy \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:PutObject","Resource":"arn:aws:s3:::your-testimonials-bucket/testimonials/*"}]}'
```

### Create the Lambda function
```bash
aws lambda create-function \
  --function-name testimonial-presign \
  --runtime nodejs20.x \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/testimonial-lambda-role \
  --handler index.handler \
  --zip-file fileb://function.zip \
  --environment Variables={BUCKET_NAME=your-testimonials-bucket}
```

---

## 3. Create API Gateway (HTTP API)

```bash
# Create HTTP API
aws apigatewayv2 create-api \
  --name testimonial-api \
  --protocol-type HTTP \
  --cors-configuration AllowOrigins='["*"]',AllowMethods='["POST","OPTIONS"]',AllowHeaders='["Content-Type"]'
```

Then in the AWS Console (easiest):
- Add a POST route `/presign`
- Integrate it with the `testimonial-presign` Lambda
- Deploy to a stage (e.g., `prod`)
- Copy the invoke URL

---

## 4. Update the Frontend

In `frontend/index.html`, replace:
```js
const API_URL = "YOUR_API_GATEWAY_URL";
```
with your actual API Gateway URL, e.g.:
```js
const API_URL = "https://abc123.execute-api.us-east-1.amazonaws.com/prod/presign";
```

---

## 5. Upload Frontend to S3

```bash
aws s3 cp frontend/index.html s3://your-testimonials-bucket/index.html --content-type text/html
```

Make it public:
```bash
aws s3api put-bucket-policy --bucket your-testimonials-bucket --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::your-testimonials-bucket/index.html"
  }]
}'
```

Your shareable link will be:
```
http://your-testimonials-bucket.s3-website-us-east-1.amazonaws.com
```

---

## Folder Structure

```
video-testimonial/
├── frontend/
│   └── index.html        # The shareable web app
├── lambda/
│   └── index.mjs         # Pre-signed URL generator
└── SETUP.md              # This file
```
