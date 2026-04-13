# Video Testimonial App

A serverless web app that lets anyone record and submit a video testimonial. Testimonial video is stored in your S3 bucket. No server required — fully hosted on AWS using S3, CloudFront, API Gateway, and Lambda.

## Architecture

```
User (Browser)
  └── CloudFront (HTTPS) ──► S3 (index.html via OAC)
  └── API Gateway (POST /presign) ──► Lambda ──► Pre-signed S3 URL
  └── Browser uploads video directly to S3
  └── S3 Event ──► Lambda (notify) ──► SNS ──► Email
```

## Project Structure

```
video-testimonial/
├── frontend/
│   └── index.html          # Single-page web app
├── lambda-presign/
│   ├── index.py            # Pre-signed URL generator (Python)
│   └── index.mjs           # Pre-signed URL generator (Node.js)
├── lambda-notify/
│   ├── index.py            # S3 event trigger → SNS email notification (Python)
│   └── index.mjs           # S3 event trigger → SNS email notification (Node.js)
├── README.md
└── .gitignore
```

---

## Deploy via AWS Console (No CLI)

### 1. Create S3 Bucket

1. Go to **S3** → **Create bucket**
2. Set bucket name: `video-testimonials-<your-account-id>`
3. Region: `ap-south-1` (or your preferred region)
4. Leave all **Block Public Access** settings ON (bucket stays private)
5. Click **Create bucket**

### 2. Create IAM Role for Lambda

Create the role once with all required permissions — it will be shared by both Lambda functions.

1. Go to **IAM** → **Roles** → **Create role**
2. Trusted entity: **AWS service** → **Lambda** → Next
3. Attach policy: `AWSLambdaBasicExecutionRole` → Next
4. Role name: `testimonial-lambda-role` → **Create role**
5. Open the role → **Add permissions** → **Create inline policy**
6. Switch to **JSON** tab and paste:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::video-testimonials-<your-account-id>/testimonials/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::video-testimonials-<your-account-id>/testimonials/*"
    },
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "*"
    }
  ]
}
```
7. Policy name: `testimonial-lambda-policy` → **Create policy**

### 3. Deploy Lambda (presign)

1. Go to **Lambda** → **Create function**
2. Name: `testimonial-presign`, Runtime: **Python 3.12**
3. Execution role: **Use an existing role** → `testimonial-lambda-role`
4. Click **Create function**
5. In the **Code** tab, replace the default code with the contents of `lambda-presign/index.py`
6. Click **Deploy**
7. Go to **Configuration** → **Environment variables** → **Edit** → Add:
   - Key: `BUCKET_NAME`, Value: `video-testimonials-<your-account-id>`
8. Click **Save**

### 4. Create API Gateway

1. Go to **API Gateway** → **Create API** → **HTTP API** → **Build**
2. Name: `testimonial-api`
3. Click **Add integration** → **Lambda** → select `testimonial-presign`
4. Click **Next** → configure route:
   - Method: `POST`, Path: `/presign`
5. Stage name: `$default`, auto-deploy: on → **Next** → **Create**
6. Copy the **Invoke URL** (e.g. `https://<id>.execute-api.ap-south-1.amazonaws.com`)
7. Go to **CORS** (left sidebar) → **Configure** → set:
   - Allow origins: `*`
   - Allow methods: `POST, OPTIONS`
   - Allow headers: `Content-Type`
   - Click **Save**

### 5. Update Frontend

Open `frontend/index.html` and update:
```js
const API_URL = "https://<id>.execute-api.ap-south-1.amazonaws.com/presign";
```

### 6. Create CloudFront Distribution

1. Go to **CloudFront** → **Distributions** → **Create distribution**
2. Origin domain: select your S3 bucket from the dropdown
3. When prompted to select a plan, choose **Free tier** (or **Pay-as-you-go** for newer accounts)
4. Origin access: leave as default — CloudFront will automatically create an OAC and update the S3 bucket policy
5. Leave all other settings as default
6. Click **Create distribution**
7. Note the **Distribution domain name** (e.g. `xxxx.cloudfront.net`) — this is your app URL
8. Once the distribution is deployed, open it → **Settings** → **Edit** → set **Default root object** to `index.html` → **Save changes**

### 7. Verify S3 Bucket Policy (CloudFront OAC)

CloudFront should have automatically updated the S3 bucket policy in the previous step. Verify by going to **S3** → your bucket → **Permissions** → **Bucket policy** and confirming a policy like this exists:

<details>
<summary>Expected bucket policy (click to expand)</summary>

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

If the policy is missing, paste the above (with your values filled in) and click **Save changes**.

</details>

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

1. Go to **SNS** → **Topics** → **Create topic** → **Standard** → name: `testimonial-notify` → **Create**
2. Click **Create subscription** → Protocol: **Email** → enter your email → **Create subscription**
3. Confirm the subscription from your inbox
4. Go to **Lambda** → **Create function** → name: `testimonial-notify`, runtime: **Python 3.12**, role: `testimonial-lambda-role`
5. In the **Code** tab, replace the default code with the contents of `lambda-notify/index.py`
6. Click **Deploy**
7. Add environment variable: `TOPIC_ARN` = your SNS topic ARN
8. Go to **Configuration** → **Triggers** → **Add trigger** → **S3**
   - Bucket: your bucket
   - Event type: **PUT**
   - Prefix: `testimonials/`
   - Click **Add**

### Done

Your app is live at: `https://<distribution-domain>.cloudfront.net`

---

## Deploy via CLI

<details>
<summary>Click to expand CLI deployment steps</summary>

### Prerequisites

- AWS CLI configured (`aws configure`)
- Node.js 18+ installed
- `zip` utility installed

### 1. Create S3 Bucket

```bash
BUCKET=video-testimonials-<your-account-id>
REGION=ap-south-1

aws s3api create-bucket \
  --bucket $BUCKET \
  --region $REGION \
  --create-bucket-configuration LocationConstraint=$REGION
```

### 2. Create IAM Role for Lambda

Create the role once with all required permissions upfront.

```bash
aws iam create-role \
  --role-name testimonial-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name testimonial-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name testimonial-lambda-role \
  --policy-name testimonial-lambda-policy \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {\"Effect\": \"Allow\", \"Action\": \"s3:PutObject\", \"Resource\": \"arn:aws:s3:::$BUCKET/testimonials/*\"},
      {\"Effect\": \"Allow\", \"Action\": \"s3:GetObject\", \"Resource\": \"arn:aws:s3:::$BUCKET/testimonials/*\"},
      {\"Effect\": \"Allow\", \"Action\": \"sns:Publish\", \"Resource\": \"*\"}
    ]
  }"
```

### 3. Deploy Lambda (presign)

```bash
cd lambda-presign
npm install
zip -r function.zip . --exclude "*.zip"

# Wait ~10s after role creation for IAM propagation
aws lambda create-function \
  --function-name testimonial-presign \
  --runtime nodejs20.x \
  --role arn:aws:iam::<ACCOUNT_ID>:role/testimonial-lambda-role \
  --handler index.handler \
  --zip-file fileb://function.zip \
  --environment Variables={BUCKET_NAME=$BUCKET} \
  --region $REGION
```

### 4. Create API Gateway

```bash
API_ID=$(aws apigatewayv2 create-api \
  --name testimonial-api \
  --protocol-type HTTP \
  --cors-configuration AllowOrigins='["*"]',AllowMethods='["POST","OPTIONS"]',AllowHeaders='["Content-Type"]' \
  --region $REGION \
  --query 'ApiId' --output text)

INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:$REGION:<ACCOUNT_ID>:function:testimonial-presign \
  --payload-format-version 2.0 \
  --region $REGION \
  --query 'IntegrationId' --output text)

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /presign" \
  --target "integrations/$INTEGRATION_ID" \
  --region $REGION

aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name '$default' \
  --auto-deploy \
  --region $REGION

aws lambda add-permission \
  --function-name testimonial-presign \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$REGION:<ACCOUNT_ID>:$API_ID/*/*/presign" \
  --region $REGION
```

API URL: `https://<API_ID>.execute-api.<REGION>.amazonaws.com/presign`

### 5. Update Frontend

```js
const API_URL = "https://<API_ID>.execute-api.<REGION>.amazonaws.com/presign";
```

### 6. Create CloudFront OAC + Distribution

```bash
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

### 7. Set S3 Bucket Policy

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

### 8. Set S3 CORS

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

### 9. Upload Frontend

```bash
aws s3 cp frontend/index.html s3://$BUCKET/index.html --content-type text/html
```

### 10. Deploy Lambda (notify) — Optional

```bash
cd ../lambda-notify
npm install
zip -r function.zip . --exclude "*.zip"

SNS_TOPIC_ARN=$(aws sns create-topic --name testimonial-notify --region $REGION --query 'TopicArn' --output text)

aws sns subscribe \
  --topic-arn $SNS_TOPIC_ARN \
  --protocol email \
  --notification-endpoint <your-email> \
  --region $REGION

aws lambda create-function \
  --function-name testimonial-notify \
  --runtime nodejs20.x \
  --role arn:aws:iam::<ACCOUNT_ID>:role/testimonial-lambda-role \
  --handler index.handler \
  --zip-file fileb://function.zip \
  --environment Variables={TOPIC_ARN=$SNS_TOPIC_ARN} \
  --region $REGION

aws lambda add-permission \
  --function-name testimonial-notify \
  --statement-id s3-invoke \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::$BUCKET \
  --region $REGION

aws s3api put-bucket-notification-configuration \
  --bucket $BUCKET \
  --notification-configuration "{
    \"LambdaFunctionConfigurations\": [{
      \"LambdaFunctionArn\": \"arn:aws:lambda:$REGION:<ACCOUNT_ID>:function:testimonial-notify\",
      \"Events\": [\"s3:ObjectCreated:Put\"],
      \"Filter\": {\"Key\": {\"FilterRules\": [{\"Name\": \"prefix\", \"Value\": \"testimonials/\"}]}}
    }]
  }"
```

### 11. (Optional) Custom Domain

1. Issue an ACM certificate in `us-east-1` for your domain
2. Add the domain as a CloudFront alias and attach the cert
3. Create a DNS CNAME: `your-domain.com` → `<dist>.cloudfront.net`

</details>

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
