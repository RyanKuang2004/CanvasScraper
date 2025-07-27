#!/bin/bash

# Canvas Scraper AWS Deployment Script
# Usage: ./deploy-aws.sh [environment-name] [aws-region]

set -e

# Configuration
ENVIRONMENT_NAME=${1:-canvas-scraper}
AWS_REGION=${2:-us-east-1}
KEY_PAIR_NAME="${ENVIRONMENT_NAME}-keypair"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Canvas Scraper AWS Deployment${NC}"
echo -e "${BLUE}Environment: ${ENVIRONMENT_NAME}${NC}"
echo -e "${BLUE}Region: ${AWS_REGION}${NC}"
echo

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install AWS CLI first.${NC}"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured. Run 'aws configure' first.${NC}"
    exit 1
fi

# Check required environment variables
if [[ -z "$CANVAS_API_TOKEN" ]]; then
    echo -e "${RED}❌ CANVAS_API_TOKEN environment variable not set.${NC}"
    echo "Please set it: export CANVAS_API_TOKEN='your_token_here'"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Create key pair if it doesn't exist
echo -e "${YELLOW}🔑 Creating EC2 key pair...${NC}"
if ! aws ec2 describe-key-pairs --key-names "$KEY_PAIR_NAME" --region "$AWS_REGION" &> /dev/null; then
    aws ec2 create-key-pair \
        --key-name "$KEY_PAIR_NAME" \
        --region "$AWS_REGION" \
        --query 'KeyMaterial' \
        --output text > ~/.ssh/${KEY_PAIR_NAME}.pem
    
    chmod 400 ~/.ssh/${KEY_PAIR_NAME}.pem
    echo -e "${GREEN}✅ Key pair created and saved to ~/.ssh/${KEY_PAIR_NAME}.pem${NC}"
else
    echo -e "${GREEN}✅ Key pair already exists${NC}"
fi

# Deploy CloudFormation stack
echo -e "${YELLOW}☁️ Deploying CloudFormation stack...${NC}"
aws cloudformation deploy \
    --template-file aws-infrastructure.yml \
    --stack-name "${ENVIRONMENT_NAME}-infrastructure" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --parameter-overrides \
        EnvironmentName="$ENVIRONMENT_NAME" \
        KeyPairName="$KEY_PAIR_NAME" \
        CanvasAPIToken="$CANVAS_API_TOKEN" \
        SupabaseURL="${SUPABASE_URL:-}" \
        SupabaseAnonKey="${SUPABASE_ANON_KEY:-}"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ CloudFormation stack deployed successfully${NC}"
else
    echo -e "${RED}❌ CloudFormation deployment failed${NC}"
    exit 1
fi

# Get instance information
echo -e "${YELLOW}📊 Getting instance information...${NC}"
INSTANCE_IP=$(aws cloudformation describe-stacks \
    --stack-name "${ENVIRONMENT_NAME}-infrastructure" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`InstancePublicIP`].OutputValue' \
    --output text)

INSTANCE_ID=$(aws cloudformation describe-stacks \
    --stack-name "${ENVIRONMENT_NAME}-infrastructure" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
    --output text)

echo -e "${GREEN}✅ Instance created successfully${NC}"
echo -e "${BLUE}Instance ID: ${INSTANCE_ID}${NC}"
echo -e "${BLUE}Public IP: ${INSTANCE_IP}${NC}"

# Wait for instance to be ready
echo -e "${YELLOW}⏳ Waiting for instance to be ready...${NC}"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
echo -e "${GREEN}✅ Instance is running${NC}"

# Wait for SSH to be available
echo -e "${YELLOW}⏳ Waiting for SSH to be available...${NC}"
for i in {1..30}; do
    if ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem -o ConnectTimeout=5 -o StrictHostKeyChecking=no ec2-user@$INSTANCE_IP "echo 'SSH ready'" &> /dev/null; then
        echo -e "${GREEN}✅ SSH is available${NC}"
        break
    fi
    echo "Attempt $i/30..."
    sleep 10
done

# Deploy application code
echo -e "${YELLOW}📦 Deploying application code...${NC}"

# Create temporary deployment package
TEMP_DIR=$(mktemp -d)
cp -r . "$TEMP_DIR/canvas-scraper"
cd "$TEMP_DIR"

# Remove unnecessary files
rm -rf canvas-scraper/.git
rm -rf canvas-scraper/venv
rm -rf canvas-scraper/__pycache__

# Create tarball
tar -czf canvas-scraper.tar.gz canvas-scraper/

# Copy to instance
scp -i ~/.ssh/${KEY_PAIR_NAME}.pem -o StrictHostKeyChecking=no \
    canvas-scraper.tar.gz ec2-user@$INSTANCE_IP:/home/ec2-user/

# Extract and build on instance
ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem -o StrictHostKeyChecking=no ec2-user@$INSTANCE_IP << 'ENDSSH'
# Extract application
cd /home/ec2-user
tar -xzf canvas-scraper.tar.gz
mv canvas-scraper/* .
rm -rf canvas-scraper canvas-scraper.tar.gz

# Build and start the application
sudo docker build -t canvas-scraper:latest .

# Create environment file
cat > .env << EOF
CANVAS_API_TOKEN=$(aws ssm get-parameter --name "/canvas-scraper/canvas-api-token" --with-decryption --region us-east-1 --query 'Parameter.Value' --output text)
SUPABASE_URL=$(aws ssm get-parameter --name "/canvas-scraper/supabase-url" --region us-east-1 --query 'Parameter.Value' --output text 2>/dev/null || echo "")
SUPABASE_ANON_KEY=$(aws ssm get-parameter --name "/canvas-scraper/supabase-anon-key" --with-decryption --region us-east-1 --query 'Parameter.Value' --output text 2>/dev/null || echo "")
EOF

# Start the container
sudo docker run -d \
    --name canvas-scraper \
    --restart unless-stopped \
    --env-file .env \
    -v /home/ec2-user/logs:/app/logs \
    canvas-scraper:latest

echo "Application deployed and started"
ENDSSH

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo -e "${GREEN}✅ Application deployed successfully${NC}"

# Show connection information
echo
echo -e "${BLUE}🎉 Deployment Complete!${NC}"
echo -e "${BLUE}===================${NC}"
echo
echo -e "${YELLOW}SSH Access:${NC}"
echo "ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ec2-user@${INSTANCE_IP}"
echo
echo -e "${YELLOW}Application Logs:${NC}"
echo "ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ec2-user@${INSTANCE_IP} 'sudo docker logs canvas-scraper'"
echo
echo -e "${YELLOW}CloudWatch Logs:${NC}"
echo "https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logStream:group=${ENVIRONMENT_NAME}-logs"
echo
echo -e "${YELLOW}Monitor Application:${NC}"
echo "ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ec2-user@${INSTANCE_IP} 'sudo docker stats canvas-scraper'"
echo
echo -e "${GREEN}🚀 Your Canvas Scraper is now running on AWS!${NC}"