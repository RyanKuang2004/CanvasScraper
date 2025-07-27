#!/bin/bash

# Canvas Scraper Deployment Script for AWS EC2
# Usage: ./deploy.sh [environment] [region]

set -e

# Configuration
ENVIRONMENT=${1:-canvas-scraper}
REGION=${2:-us-east-1}
STACK_NAME="${ENVIRONMENT}-infrastructure"
KEY_PAIR_NAME="${ENVIRONMENT}-keypair"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed. Please install it first."
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install it first."
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured. Run 'aws configure' first."
    fi
    
    log "Prerequisites check passed!"
}

# Create EC2 Key Pair if it doesn't exist
create_key_pair() {
    log "Checking for EC2 key pair: ${KEY_PAIR_NAME}..."
    
    if aws ec2 describe-key-pairs --key-names "${KEY_PAIR_NAME}" --region "${REGION}" &> /dev/null; then
        log "Key pair ${KEY_PAIR_NAME} already exists."
    else
        log "Creating new key pair: ${KEY_PAIR_NAME}..."
        aws ec2 create-key-pair \
            --key-name "${KEY_PAIR_NAME}" \
            --region "${REGION}" \
            --query 'KeyMaterial' \
            --output text > ~/.ssh/"${KEY_PAIR_NAME}".pem
        
        chmod 400 ~/.ssh/"${KEY_PAIR_NAME}".pem
        log "Key pair created and saved to ~/.ssh/${KEY_PAIR_NAME}.pem"
    fi
}

# Get Canvas API Token securely
get_canvas_token() {
    if [ -z "${CANVAS_API_TOKEN}" ]; then
        echo -n "Enter your Canvas API Token: "
        read -s CANVAS_API_TOKEN
        echo
        
        if [ -z "${CANVAS_API_TOKEN}" ]; then
            error "Canvas API Token is required!"
        fi
    fi
}

# Deploy CloudFormation stack
deploy_infrastructure() {
    log "Deploying infrastructure stack: ${STACK_NAME}..."
    
    # Get your current IP for security group
    MY_IP=$(curl -s https://checkip.amazonaws.com/)
    if [ -z "${MY_IP}" ]; then
        warn "Could not determine your public IP. Using 0.0.0.0/0 (less secure)"
        MY_IP="0.0.0.0"
    fi
    
    aws cloudformation deploy \
        --template-file ../aws/cloudformation.yml \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --parameter-overrides \
            EnvironmentName="${ENVIRONMENT}" \
            KeyPairName="${KEY_PAIR_NAME}" \
            AllowedCIDR="${MY_IP}/32" \
            CanvasAPIToken="${CANVAS_API_TOKEN}" \
        --tags \
            Environment="${ENVIRONMENT}" \
            Project="canvas-scraper" \
            DeployedBy="$(aws sts get-caller-identity --query Arn --output text)"
    
    log "Infrastructure deployment completed!"
}

# Get instance information
get_instance_info() {
    log "Retrieving instance information..."
    
    INSTANCE_IP=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`InstancePublicIP`].OutputValue' \
        --output text)
    
    INSTANCE_ID=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
        --output text)
    
    log "Instance ID: ${INSTANCE_ID}"
    log "Instance IP: ${INSTANCE_IP}"
    log "SSH Command: ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ec2-user@${INSTANCE_IP}"
}

# Wait for instance to be ready
wait_for_instance() {
    log "Waiting for instance to be ready..."
    
    # Wait for instance status checks to pass
    aws ec2 wait instance-status-ok \
        --instance-ids "${INSTANCE_ID}" \
        --region "${REGION}"
    
    # Wait for SSH to be available
    log "Waiting for SSH to be available..."
    for i in {1..30}; do
        if ssh -i ~/.ssh/"${KEY_PAIR_NAME}".pem \
               -o ConnectTimeout=5 \
               -o StrictHostKeyChecking=no \
               ec2-user@"${INSTANCE_IP}" \
               "echo 'SSH is ready'" &> /dev/null; then
            log "SSH is now available!"
            break
        fi
        
        if [ $i -eq 30 ]; then
            error "Timeout waiting for SSH access"
        fi
        
        log "Attempt $i/30: SSH not ready yet, waiting..."
        sleep 10
    done
}

# Deploy application
deploy_application() {
    log "Deploying Canvas Scraper application..."
    
    # Create deployment directory on instance
    ssh -i ~/.ssh/"${KEY_PAIR_NAME}".pem \
        -o StrictHostKeyChecking=no \
        ec2-user@"${INSTANCE_IP}" \
        "mkdir -p ~/canvas-scraper"
    
    # Copy application files
    scp -i ~/.ssh/"${KEY_PAIR_NAME}".pem \
        -o StrictHostKeyChecking=no \
        -r ../{*.py,requirements.txt,Dockerfile,docker-compose.yml} \
        ec2-user@"${INSTANCE_IP}":~/canvas-scraper/
    
    # Build and run the application
    ssh -i ~/.ssh/"${KEY_PAIR_NAME}".pem \
        -o StrictHostKeyChecking=no \
        ec2-user@"${INSTANCE_IP}" << 'EOF'
cd ~/canvas-scraper

# Build Docker image
sudo docker build -t canvas-scraper:latest .

# Run the application
sudo docker-compose up -d

# Check status
sudo docker-compose ps
sudo docker-compose logs --tail=20
EOF
    
    log "Application deployment completed!"
}

# Main deployment function
main() {
    log "Starting Canvas Scraper deployment to AWS EC2..."
    log "Environment: ${ENVIRONMENT}"
    log "Region: ${REGION}"
    
    check_prerequisites
    create_key_pair
    get_canvas_token
    deploy_infrastructure
    get_instance_info
    wait_for_instance
    deploy_application
    
    log "Deployment completed successfully!"
    log ""
    log "=== Deployment Summary ==="
    log "Instance ID: ${INSTANCE_ID}"
    log "Public IP: ${INSTANCE_IP}"
    log "SSH Access: ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ec2-user@${INSTANCE_IP}"
    log "Application logs: ssh to instance and run 'sudo docker-compose logs -f'"
    log ""
    log "To clean up resources, run: aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}"
}

# Show help
show_help() {
    echo "Canvas Scraper AWS Deployment Script"
    echo ""
    echo "Usage: $0 [environment] [region]"
    echo ""
    echo "Arguments:"
    echo "  environment  Environment name (default: canvas-scraper)"
    echo "  region       AWS region (default: us-east-1)"
    echo ""
    echo "Environment Variables:"
    echo "  CANVAS_API_TOKEN  Canvas API token (will prompt if not set)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Deploy to default environment and region"
    echo "  $0 production us-west-2      # Deploy to production in us-west-2"
    echo ""
    echo "Prerequisites:"
    echo "  - AWS CLI installed and configured"
    echo "  - Docker installed"
    echo "  - Valid Canvas API token"
}

# Handle command line arguments
case "${1:-}" in
    -h|--help|help)
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac