# Video Testimonial App

A serverless web app that lets anyone record and submit a video testimonial for the **AWS Solutions Architect Associate course by Chetan Agrawal** on Udemy. No server required — fully hosted on AWS using S3, CloudFront, API Gateway, and Lambda.

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

## File Structure

```
video-testimonial/
├── frontend/
│   └── index.html       # Single-page web app
├── lambda/
│   └── index.mjs        # Pre-signed URL generator
├── README.md
└── .gitignore
```
