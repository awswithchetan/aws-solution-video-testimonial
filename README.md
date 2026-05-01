# Video Testimonial App

This repo is a part of my youtube video where I have explained the architecture and detailed steps to deploy this application:

Video: https://youtu.be/KUjDQNJBAks

## Application
A serverless web app to ask for video testimonial for your product or services. Testimonial video can be recorded using mobile phone or desktop and when submitted its uploaded to your private S3 bucket. 

This is fully Serverless Application hosted on AWS using Amazon S3, CloudFront, API Gateway, Lambda and SNS.

## Architecture
<img width="900" height="480" alt="image" src="https://github.com/user-attachments/assets/a6f36fd5-94fe-408b-a6ca-666ebffcb3da" />


```
User (Browser)
1. DNS request for custom domain -> Resolved by Amazon Route53
2. HTTPS request to CloudFront -> S3 (via OAC)
3. User records video using browser and submits -> API gateway (POST /presign) request
4. Triggers Lambda -> Generate S3 pre-sign URL -> Return pre-signed URL
5. Start upload using pre-signed URL
6. Upload complete -> S3 Event notification -> Lambda -> SNS -> Email
```

## Project Structure

```
video-testimonial/
├── frontend/
│   └── index.html          # Single-page web app
├── lambda-presign/
│   ├── lambda_function.py  # Pre-signed URL generator (Python)
├── lambda-notify/
│   ├── lambda_function.py  # S3 event trigger → SNS email notification (Python)
├── README.md
└── .gitignore
```

---

## Prerequisites

1. **AWS Account and IAM User** — An AWS account with an IAM user with admin access (Access for S3, Lambda, API Gateway, CloudFront, SNS, and IAM resources)
2. **Local Workstation** — To clone this repository and modify/upload frontend code
3. **AWS CLI** — [Install and configure](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
4. **Public Hosted Zone in Route 53** (optional) — A registered domain with Route 53 as the DNS provider

> Need help with any of the above? Check out my [AWS YouTube playlist](https://www.youtube.com/playlist?list=PLIUhw5xEbE-WI2s0qoo3tKaiVlkz0pLIl).

---

## Deployment Steps

### Clone git repository in local workstation:
```bash
git clone https://github.com/awswithchetan/aws-solution-video-testimonial.git
cd aws-solution-video-testimonial
```

### Module 1 — Frontend Infrastructure

### 1. Create S3 Bucket

1. Go to **S3** → **Create bucket**
2. Set bucket name: `testimonial-<your-account-id>`
3. Region: `ap-south-1` (or your preferred region)
4. Leave all **Block Public Access** settings ON (bucket stays private)
5. Click **Create bucket**

### 2. Create CloudFront Distribution

1. Go to **CloudFront** → **Distributions** → **Create distribution**
2. When prompted to select a plan, choose **Free tier** (or **Pay-as-you-go** for newer accounts)
3. Origin domain: select your S3 bucket from the dropdown
4. Origin access: leave as default — CloudFront will automatically create an OAC and update the S3 bucket policy
5. Click **Next**
6. When prompted for security protections, select **Do not enable security protections**
7. Leave all other settings as default
8. Click **Create distribution**
9. Note the **Distribution domain name** (e.g. `xxxx.cloudfront.net`) — this is your app URL

### 3. Set Default Root Object

1. Open the distribution → **General** tab → **Edit**
2. Set **Default root object** to `index.html`
3. Click **Save changes**

### 4. Verify S3 Bucket Policy (CloudFront OAC)

CloudFront should have automatically updated the S3 bucket policy. Verify by going to **S3** → your bucket → **Permissions** → **Bucket policy** and confirming a policy like this exists:

<details>
<summary>Expected bucket policy (click to expand)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "cloudfront.amazonaws.com"},
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::testimonial-<your-account-id>/*",
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

### 5. Set S3 CORS

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

---

### Module 2 — Backend

### 6. Create IAM Role for Lambda

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
      "Resource": "arn:aws:s3:::testimonial-<your-account-id>/testimonials/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::testimonial-<your-account-id>/testimonials/*"
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

### 7. Deploy Lambda (presign)

1. Go to **Lambda** → **Create function**
2. Name: `testimonial-presign`, Runtime: **Python 3.14**
3. Expand **Change default execution role** → select **Use an existing role** → `testimonial-lambda-role`
4. Click **Create function**
5. In the **Code** tab, replace the default code with the contents of `lambda-presign/lambda_function.py`
6. Click **Deploy**
7. Go to **Configuration** → **General configuration** → **Edit** → set **Timeout** to `0 min 30 sec` → **Save**
8. Go to **Configuration** → **Environment variables** → **Edit** → Add:
   - Key: `BUCKET_NAME`, Value: `testimonial-<your-account-id>`
9. Click **Save**

---

### Module 3 — API Layer

### 8. Create API Gateway

1. Go to **API Gateway** → **Create API** → **HTTP API** → **Build**
2. Name: `testimonial-api`
3. Click **Add integration** → **Lambda** → select `testimonial-presign`
4. Click **Next** → configure route:
   - Method: `POST`, Path: `/presign`
   - Integration target: select `testimonial-presign`
5. Stage name: `$default`, auto-deploy: on → **Next** → **Create**
6. Copy the **Invoke URL** (e.g. `https://<id>.execute-api.<region>.amazonaws.com`)
7. Go to **CORS** (left sidebar) → **Configure** → set:
   - Allow origins: `*` → click **Add**
   - Allow methods: `POST, OPTIONS` → click **Add**
   - Allow headers: `Content-Type` → click **Add**
   - Click **Save**

---

### Module 4 — Integration & Test

### 9. Update Frontend

Open `frontend/index.html` and update the config block at the top of the `<script>` section:
```js
const API_URL    = "https://<id>.execute-api.<region>.amazonaws.com/presign"; // your API Gateway URL
const PAGE_TITLE    = "Share your Testimonial";       // customize the page heading
const PAGE_SUBTITLE = "Record a short video ...";     // customize the subheading
const TIP_SCRIPT = [ ... ];                           // customize the recording tips
```

### 10. Upload Frontend to S3

1. Go to **S3** → your bucket → **Upload**
2. Upload `frontend/index.html`
3. Expand **Additional upload options** → set **Content type** to `text/html`
4. Click **Upload**

Or via CLI:
```bash
aws s3 cp frontend/index.html s3://<your-bucket>/index.html --content-type text/html
```

### ✅ Validate Your Deployment

Before proceeding, verify the core app is working:

1. Open `https://<distribution-domain>.cloudfront.net` in your browser
2. Enter your name and record or upload a short video
3. Click **Submit Testimonial** — you should see the success message
4. Go to **S3** → your bucket → `testimonials/` folder and confirm the video and companion `.json` file are present

If the upload succeeds, your app is fully working. Steps 11–12 below add email notifications on top of this.

---

### Module 5 — Notifications

### 11. Create SNS Topic for Notifications

1. Go to **SNS** → **Topics** → **Create topic** → **Standard**
2. Name: `testimonial-notify` → **Create topic**
3. Click **Create subscription** → Protocol: **Email** → enter your email → **Create subscription**
4. Confirm the subscription from your inbox

### 12. Deploy Lambda (notify)

1. Go to **Lambda** → **Create function**
2. Name: `testimonial-notify`, Runtime: **Python 3.14**
3. Expand **Change default execution role** → select **Use an existing role** → `testimonial-lambda-role`
4. Click **Create function**
5. In the **Code** tab, replace the default code with the contents of `lambda-notify/lambda_function.py`
6. Click **Deploy**
7. Go to **Configuration** → **General configuration** → **Edit** → set **Timeout** to `0 min 30 sec` → **Save**
8. Go to **Configuration** → **Environment variables** → **Edit** → Add:
   - Key: `TOPIC_ARN`, Value: your SNS topic ARN
9. Click **Save**
10. Go to **Configuration** → **Triggers** → **Add trigger** → **S3**
    - Bucket: your bucket
    - Event type: **PUT**
    - Prefix: `testimonials/`
    - Click **Add**

### Congratulations 🎉

Your app is live at: `https://<distribution-domain>.cloudfront.net`

---

##  (Optional) Module 6 - Custom Domain and SSL

### Prerequisites
- A registered domain name
- Amazon Route 53 configured as the DNS provider for your domain (Hosted Zone exists)

> Need help? Watch [How to buy a domain and configure Route 53](https://youtu.be/vaI5rSNtBf0) on YouTube.

### 1. Request SSL Certificate in ACM

> ⚠️ Certificate must be requested in **us-east-1** regardless of your app's region — CloudFront requires it.

1. Go to **ACM** → switch to **us-east-1** region → **Request certificate** → **Request a public certificate**
2. Add domain name: `testimonial.yourdomain.com` (or `review.yourdomain.com`) — or use `*.yourdomain.com` to cover all subdomains
3. Validation method: **DNS validation** → **Request**
4. Open the certificate → click **Create records in Route 53** → confirm
5. Wait for status to change to **Issued** (usually 1–2 minutes)

### 2. Add Alternate Domain to CloudFront

1. Go to **CloudFront** → your distribution → **Settings** → **Edit**
2. Alternate domain names (CNAMEs): add `testimonial.yourdomain.com` (or `review.yourdomain.com`)
3. Custom SSL certificate: select the ACM certificate you just issued
4. **Save changes** → wait for deployment (5–10 minutes)

### 3. Create Route 53 DNS Record

1. Go to **Route 53** → **Hosted zones** → your domain → **Create record**
2. Record name: `testimonial` (or `review`), Record type: **A**, toggle **Alias** on
3. Route traffic to: **Alias to CloudFront distribution** → select your distribution
4. **Create records**

Your app is now accessible at `https://testimonial.yourdomain.com`

---

## Deploy via CLI

<details>
<summary>Click to expand CLI deployment steps</summary>

### Prerequisites

- AWS CLI configured (`aws configure`)
- Python 3.14+ installed
- `zip` utility installed

### 1. Create S3 Bucket

```bash
BUCKET=testimonial-<your-account-id>
REGION=<your-region>

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
zip -j function.zip lambda_function.py

# Wait ~10s after role creation for IAM propagation
aws lambda create-function \
  --function-name testimonial-presign \
  --runtime python3.13 \
  --role arn:aws:iam::<ACCOUNT_ID>:role/testimonial-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
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
const API_URL    = "https://<API_ID>.execute-api.<REGION>.amazonaws.com/presign";
const PAGE_TITLE    = "Share your Testimonial";
const PAGE_SUBTITLE = "Record a short video ...";
const TIP_SCRIPT = [ ... ];
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

### 11. Create SNS Topic for Notifications

```bash
SNS_TOPIC_ARN=$(aws sns create-topic --name testimonial-notify --region $REGION --query 'TopicArn' --output text)

aws sns subscribe \
  --topic-arn $SNS_TOPIC_ARN \
  --protocol email \
  --notification-endpoint <your-email> \
  --region $REGION
```

Confirm the subscription from your inbox before proceeding.

### 12. Deploy Lambda (notify)

```bash
cd ../lambda-notify
zip -j function.zip lambda_function.py

aws lambda create-function \
  --function-name testimonial-notify \
  --runtime python3.13 \
  --role arn:aws:iam::<ACCOUNT_ID>:role/testimonial-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
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

### 12. (Optional) Custom Domain

1. Issue an ACM certificate in `us-east-1` for your domain
2. Add the domain as a CloudFront alias and attach the cert
3. Create a DNS CNAME: `your-domain.com` → `<dist>.cloudfront.net`

</details>

---

## Module 7 - Cleanup

To delete all resources and avoid ongoing charges:

1. **S3** → your bucket → **Empty** the bucket first, then **Delete** it
2. **Lambda** → delete `testimonial-presign` and `testimonial-notify`
3. **API Gateway** → delete `testimonial-api`
4. **CloudFront** → disable the distribution first → wait for it to deploy → then **Delete** it
5. **SNS** → delete the `testimonial-notify` topic
6. **IAM** → delete the `testimonial-lambda-role` role

> CloudFront must be disabled before it can be deleted. Disabling takes a few minutes to propagate.

---

## Viewing Submissions

Videos are stored under `s3://<bucket>/testimonials/`. Each video has a companion `.json` file with the submitter's details:
- `name` — submitter's name
- `email` — submitter's email (if provided)
- `consent` — `true` / `false`

View via AWS Console → S3 → your bucket → `testimonials/` folder, or:

```bash
aws s3 ls s3://$BUCKET/testimonials/ --region $REGION
```
