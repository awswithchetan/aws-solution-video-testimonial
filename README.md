# Video Testimonial App

A serverless web app that lets anyone record and submit a video testimonial. Testimonial video is stored in your S3 bucket. No server required — fully hosted on AWS using S3, CloudFront, API Gateway, and Lambda.

## Architecture

```
User (Browser)
  └── CloudFront (HTTPS) ──► S3 (index.html via OAC)
  └── API Gateway (POST /presign) ──► Lambda ──► Pre-signed S3 URL
  └── Browser uploads video directly to S3
```

## Prerequisites

- AWS CLI configured (`aws configure`)
- Node.js 18+ installed
- `zip` utility installed

---

## Deploy

### 1. Create S3 Bucket

```bash
BUCKET=video-testimonials-<your-account-id>
REGION=ap-south-1

aws s3api create-bucket \
  --bucket $BUCKET \
  --region $REGION \
  --create-bucket-configuration LocationConstraint=$REGION
```

### 2. Deploy Lambda

```bash
cd lambda
npm install
zip -r function.zip . --exclude "*.zip"

# Create IAM role
aws iam create-role \
  --role-name testimonial-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name testimonial-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name testimonial-lambda-role \
  --policy-name s3-put-policy \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"s3:PutObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/testimonials/*\"}]}"

# Wait ~10s for role to propagate, then create function
aws lambda create-function \
  --function-name testimonial-presign \
  --runtime nodejs20.x \
  --role arn:aws:iam::<ACCOUNT_ID>:role/testimonial-lambda-role \
  --handler index.handler \
  --zip-file fileb://function.zip \
  --environment Variables={BUCKET_NAME=$BUCKET} \
  --region $REGION
```

### 3. Create API Gateway

```bash
# Create HTTP API
API_ID=$(aws apigatewayv2 create-api \
  --name testimonial-api \
  --protocol-type HTTP \
  --cors-configuration AllowOrigins='["*"]',AllowMethods='["POST","OPTIONS"]',AllowHeaders='["Content-Type"]' \
  --region $REGION \
  --query 'ApiId' --output text)

# Create Lambda integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:$REGION:<ACCOUNT_ID>:function:testimonial-presign \
  --payload-format-version 2.0 \
  --region $REGION \
  --query 'IntegrationId' --output text)

# Create route and stage
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /presign" \
  --target "integrations/$INTEGRATION_ID" \
  --region $REGION

aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name prod \
  --auto-deploy \
  --region $REGION

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name testimonial-presign \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$REGION:<ACCOUNT_ID>:$API_ID/*/*/presign" \
  --region $REGION
```

API URL will be: `https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod/presign`

### 4. Update Frontend

In `frontend/index.html`, set `API_URL` to your API Gateway URL:

```js
const API_URL = "https://<API_ID>.execute-api.<REGION>.amazonaws.com/prod/presign";
```

### 5. Create CloudFront OAC + Distribution

```bash
# Create OAC
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config '{
    "Name": "testimonial-oac",
    "OriginAccessControlOriginType": "s3",
    "SigningBehavior": "always",
    "SigningProtocol": "sigv4",
    "Description": ""
  }' \
  --region us-east-1 \
  --query 'OriginAccessControl.Id' --output text)

# Create CloudFront distribution
DIST_ID=$(aws cloudfront create-distribution \
  --distribution-config "{
    \"CallerReference\": \"testimonial-$(date +%s)\",
    \"DefaultRootObject\": \"index.html\",
    \"Origins\": {
      \"Quantity\": 1,
      \"Items\": [{
        \"Id\": \"s3-oac-origin\",
        \"DomainName\": \"$BUCKET.s3.$REGION.amazonaws.com\",
        \"S3OriginConfig\": {\"OriginAccessIdentity\": \"\"},
        \"OriginAccessControlId\": \"$OAC_ID\"
      }]
    },
    \"DefaultCacheBehavior\": {
      \"TargetOriginId\": \"s3-oac-origin\",
      \"ViewerProtocolPolicy\": \"redirect-to-https\",
      \"CachePolicyId\": \"658327ea-f89d-4fab-a63d-7e88639e58f6\",
      \"AllowedMethods\": {\"Quantity\": 2, \"Items\": [\"GET\", \"HEAD\"]}
    },
    \"Comment\": \"Video Testimonial App\",
    \"Enabled\": true
  }" \
  --region us-east-1 \
  --query 'Distribution.Id' --output text)
```

### 6. Set S3 Bucket Policy (private, CloudFront OAC only)

```bash
aws s3api put-bucket-policy \
  --bucket $BUCKET \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Principal\": {\"Service\": \"cloudfront.amazonaws.com\"},
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::$BUCKET/*\",
      \"Condition\": {
        \"StringEquals\": {
          \"AWS:SourceArn\": \"arn:aws:cloudfront::<ACCOUNT_ID>:distribution/$DIST_ID\"
        }
      }
    }]
  }"

aws s3api put-public-access-block \
  --bucket $BUCKET \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 7. Set S3 CORS (for direct browser uploads via pre-signed URL)

```bash
aws s3api put-bucket-cors \
  --bucket $BUCKET \
  --cors-configuration '{
    "CORSRules": [{
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["PUT", "GET"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }]
  }'
```

### 8. Upload Frontend

```bash
aws s3 cp frontend/index.html s3://$BUCKET/index.html --content-type text/html
```

### 9. (Optional) Custom Domain

1. Issue an ACM certificate in `us-east-1` for your domain
2. Add the domain as a CloudFront alias and attach the cert
3. Create a DNS CNAME: `your-domain.com` → `<dist>.cloudfront.net`

---

## Viewing Submissions

Videos are stored under `s3://<bucket>/testimonials/`. Each object has metadata:
- `name` — submitter's name
- `email` — submitter's email (if provided)
- `consent` — `true` / `false`

View via AWS Console → S3 → your bucket → `testimonials/` folder, or:

```bash
aws s3 ls s3://$BUCKET/testimonials/ --region $REGION
```

---

## Deploy via AWS Console (No CLI)

A step-by-step guide to deploy the entire app using only the AWS Management Console.

### 1. Create S3 Bucket

1. Go to **S3** → **Create bucket**
2. Set bucket name: `video-testimonials-<your-account-id>`
3. Region: `ap-south-1` (or your preferred region)
4. Uncheck **Block all public access** — leave all blocks ON (bucket stays private)
5. Click **Create bucket**

### 2. Create IAM Role for Lambda

1. Go to **IAM** → **Roles** → **Create role**
2. Trusted entity: **AWS service** → **Lambda** → Next
3. Attach policy: `AWSLambdaBasicExecutionRole` → Next
4. Role name: `testimonial-lambda-role` → **Create role**
5. Open the role → **Add permissions** → **Create inline policy**
6. Switch to **JSON** tab and paste:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::video-testimonials-<your-account-id>/testimonials/*"
  }]
}
```
7. Policy name: `s3-put-policy` → **Create policy**

### 3. Deploy Lambda (presign)

1. Go to **Lambda** → **Create function**
2. Name: `testimonial-presign`, Runtime: **Node.js 20.x**
3. Execution role: **Use an existing role** → `testimonial-lambda-role`
4. Click **Create function**
5. In the **Code** tab → **Upload from** → **.zip file** → upload `lambda/function.zip`
6. Set handler to `index.handler`
7. Go to **Configuration** → **Environment variables** → **Edit** → Add:
   - Key: `BUCKET_NAME`, Value: `video-testimonials-<your-account-id>`
8. Click **Save**

### 4. Create API Gateway

1. Go to **API Gateway** → **Create API** → **HTTP API** → **Build**
2. Name: `testimonial-api`
3. Click **Add integration** → **Lambda** → select `testimonial-presign`
4. Click **Next** → configure route:
   - Method: `POST`, Path: `/presign`
5. Stage name: `prod`, auto-deploy: on → **Next** → **Create**
6. Copy the **Invoke URL** (e.g. `https://<id>.execute-api.ap-south-1.amazonaws.com`)
7. Go to **CORS** (left sidebar) → **Configure** → set:
   - Allow origins: `*`
   - Allow methods: `POST, OPTIONS`
   - Allow headers: `Content-Type`
   - Click **Save**

### 5. Update Frontend

Open `frontend/index.html` and update:
```js
const API_URL = "https://<id>.execute-api.ap-south-1.amazonaws.com/prod/presign";
```

### 6. Create CloudFront OAC + Distribution

1. Go to **CloudFront** → **Origin access** → **Create control setting**
2. Name: `testimonial-oac`, Origin type: **S3**, Signing: **Sign requests (recommended)** → **Create**
3. Go to **Distributions** → **Create distribution**
4. Origin domain: select your S3 bucket from the dropdown
5. Origin access: **Origin access control settings** → select `testimonial-oac`
6. Click **Update bucket policy** when prompted (or do it manually in step 7)
7. Default root object: `index.html`
8. Viewer protocol policy: **Redirect HTTP to HTTPS**
9. Click **Create distribution**
10. Note the **Distribution domain name** (e.g. `xxxx.cloudfront.net`) — this is your app URL
11. Note the **Distribution ID** for the next step

### 7. Set S3 Bucket Policy (CloudFront OAC only)

1. Go to **S3** → your bucket → **Permissions** → **Bucket policy** → **Edit**
2. Paste (replace placeholders):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "cloudfront.amazonaws.com"},
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::video-testimonials-<your-account-id>/*",
    "Condition": {
      "StringEquals": {
        "AWS:SourceArn": "arn:aws:cloudfront::<your-account-id>:distribution/<distribution-id>"
      }
    }
  }]
}
```
3. Click **Save changes**

### 8. Set S3 CORS

1. Go to **S3** → your bucket → **Permissions** → **Cross-origin resource sharing (CORS)** → **Edit**
2. Paste:
```json
[{
  "AllowedOrigins": ["*"],
  "AllowedMethods": ["PUT", "GET"],
  "AllowedHeaders": ["*"],
  "MaxAgeSeconds": 3000
}]
```
3. Click **Save changes**

### 9. Upload Frontend to S3

1. Go to **S3** → your bucket → **Upload**
2. Upload `frontend/index.html`
3. Expand **Additional upload options** → set **Content type** to `text/html`
4. Click **Upload**

### 10. Deploy Lambda (notify) — Optional

1. Go to **IAM** → `testimonial-lambda-role` → add another inline policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::video-testimonials-<your-account-id>/testimonials/*"},
    {"Effect": "Allow", "Action": "sns:Publish", "Resource": "*"}
  ]
}
```
2. Go to **SNS** → **Topics** → **Create topic** → **Standard** → name: `testimonial-notify` → **Create**
3. Click **Create subscription** → Protocol: **Email** → enter your email → **Create subscription**
4. Confirm the subscription from your inbox
5. Go to **Lambda** → **Create function** → name: `testimonial-notify`, runtime: **Node.js 20.x**, role: `testimonial-lambda-role`
6. Upload `lambda-notify/function.zip`
7. Set handler to `index.handler`
8. Add environment variable: `TOPIC_ARN` = your SNS topic ARN
9. Go to **Configuration** → **Triggers** → **Add trigger** → **S3**
   - Bucket: your bucket
   - Event type: **PUT**
   - Prefix: `testimonials/`
   - Click **Add**

### Done

Your app is live at: `https://<distribution-id>.cloudfront.net`

---

## File Structure

```
video-testimonial/
├── frontend/
│   └── index.html          # Single-page web app
├── lambda/
│   └── index.mjs           # Pre-signed URL generator
├── lambda-notify/
│   └── index.mjs           # S3 event trigger → SNS email notification
├── README.md
└── .gitignore
```
