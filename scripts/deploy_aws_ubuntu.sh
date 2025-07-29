#!/bin/bash
# Canvas Scraper Enhanced - AWS Ubuntu Deployment Script
# Automated deployment script for AWS EC2 Ubuntu instances

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KEY_NAME="canvas-scraper-key"
SECURITY_GROUP="canvas-scraper-sg"
INSTANCE_TYPE="t3.medium"
UBUNTU_AMI="ami-0c7217cdde317cfec"  # Ubuntu 22.04 LTS (update as needed)

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install and configure AWS CLI first."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi
    
    # Check if AWS is configured
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI not configured. Run 'aws configure' first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

get_public_ip() {
    curl -s https://checkip.amazonaws.com/ || echo "0.0.0.0"
}

create_key_pair() {
    log_info "Creating/checking key pair..."
    
    if aws ec2 describe-key-pairs --key-names "$KEY_NAME" &> /dev/null; then
        log_warning "Key pair $KEY_NAME already exists"
    else
        log_info "Creating new key pair: $KEY_NAME"
        aws ec2 create-key-pair \
            --key-name "$KEY_NAME" \
            --query 'KeyMaterial' \
            --output text > "${KEY_NAME}.pem"
        chmod 400 "${KEY_NAME}.pem"
        log_success "Key pair created: ${KEY_NAME}.pem"
    fi
}

create_security_group() {
    log_info "Creating/checking security group..."
    
    if aws ec2 describe-security-groups --group-names "$SECURITY_GROUP" &> /dev/null; then
        log_warning "Security group $SECURITY_GROUP already exists"
        SG_ID=$(aws ec2 describe-security-groups \
            --group-names "$SECURITY_GROUP" \
            --query 'SecurityGroups[0].GroupId' \
            --output text)
    else
        log_info "Creating new security group: $SECURITY_GROUP"
        aws ec2 create-security-group \
            --group-name "$SECURITY_GROUP" \
            --description "Security group for Canvas Scraper Enhanced"
        
        SG_ID=$(aws ec2 describe-security-groups \
            --group-names "$SECURITY_GROUP" \
            --query 'SecurityGroups[0].GroupId' \
            --output text)
        
        # Get public IP for SSH access
        MY_IP=$(get_public_ip)
        log_info "Adding SSH access for IP: $MY_IP"
        
        # Add SSH access
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp \
            --port 22 \
            --cidr "${MY_IP}/32"
        
        # Add health check port
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp \
            --port 8080 \
            --cidr "0.0.0.0/0"
        
        log_success "Security group created with ID: $SG_ID"
    fi
}

launch_instance() {
    log_info "Launching EC2 instance..."
    
    # Check if instance already exists
    EXISTING_INSTANCE=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=canvas-scraper-production" "Name=instance-state-name,Values=running,pending" \
        --query 'Reservations[0].Instances[0].InstanceId' \
        --output text 2>/dev/null || echo "None")
    
    if [ "$EXISTING_INSTANCE" != "None" ] && [ "$EXISTING_INSTANCE" != "null" ]; then
        log_warning "Instance already exists: $EXISTING_INSTANCE"
        INSTANCE_ID="$EXISTING_INSTANCE"
    else
        log_info "Creating new instance..."
        INSTANCE_ID=$(aws ec2 run-instances \
            --image-id "$UBUNTU_AMI" \
            --count 1 \
            --instance-type "$INSTANCE_TYPE" \
            --key-name "$KEY_NAME" \
            --security-group-ids "$SG_ID" \
            --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=canvas-scraper-production}]' \
            --user-data '#!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose-plugin
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu' \
            --query 'Instances[0].InstanceId' \
            --output text)
        
        log_success "Instance launched: $INSTANCE_ID"
        log_info "Waiting for instance to be running..."
        aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
    fi
    
    # Get public IP
    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text)
    
    log_success "Instance ready: $PUBLIC_IP"
}

setup_environment() {
    log_info "Setting up deployment environment..."
    
    # Create deployment directory
    mkdir -p deployment/aws-ubuntu
    cd deployment/aws-ubuntu
    
    # Create environment template if it doesn't exist
    if [ ! -f .env.production ]; then
        cat > .env.production << 'EOF'
# Canvas API Configuration
CANVAS_API_TOKEN=your_canvas_api_token_here
CANVAS_URL=https://canvas.lms.unimelb.edu.au/api/v1

# Supabase Configuration (Optional but recommended)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here

# Application Configuration
LOG_LEVEL=INFO
ENABLE_CRON=true
ENABLE_HEALTH_SERVER=true
PYTHONUNBUFFERED=1

# Scheduling Configuration
CRON_SCHEDULE=0 2,14 * * *
EOF
        log_warning "Created .env.production template - please update with your credentials"
    fi
    
    # Create courses configuration if it doesn't exist
    if [ ! -f courses.yml ]; then
        cat > courses.yml << 'EOF'
# Canvas Course Configuration for Production
enabled_courses:
  - "12345"  # Replace with your actual course IDs
  - "67890"

scraping_preferences:
  file_types:
    - pdf
    - pptx
    - docx
  max_file_size_mb: 50
  skip_hidden_modules: true
  concurrent_downloads: 3

text_processing:
  chunk_size: 1000
  chunk_overlap: 200
  preserve_structure: true

scheduling:
  enabled: true
  timezone: "Australia/Melbourne"
  times:
    - "12:00"
    - "20:00"

deduplication:
  enabled: true
  check_content_changes: true
  fingerprint_algorithm: "sha256"
EOF
        log_warning "Created courses.yml template - please update with your course IDs"
    fi
    
    cd ../..
}

build_docker_image() {
    log_info "Building Docker image..."
    docker build -t canvas-scraper-enhanced .
    log_success "Docker image built successfully"
}

deploy_to_instance() {
    log_info "Deploying to EC2 instance..."
    
    # Wait for SSH to be available
    log_info "Waiting for SSH access..."
    for i in {1..30}; do
        if ssh -i "${KEY_NAME}.pem" -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@"$PUBLIC_IP" "echo 'SSH ready'" &> /dev/null; then
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "SSH connection timed out"
            exit 1
        fi
        sleep 10
    done
    
    log_success "SSH connection established"
    
    # Create application directories on remote server
    ssh -i "${KEY_NAME}.pem" ubuntu@"$PUBLIC_IP" << 'REMOTE_COMMANDS'
        sudo mkdir -p /opt/canvas-scraper/{config,logs,data,downloads}
        sudo chown -R ubuntu:ubuntu /opt/canvas-scraper
REMOTE_COMMANDS
    
    # Copy project files
    log_info "Copying project files..."
    scp -i "${KEY_NAME}.pem" -r \
        src/ scripts/ docker/ database/ tests/ requirements.txt Dockerfile \
        ubuntu@"$PUBLIC_IP":/opt/canvas-scraper/
    
    # Copy configuration files
    scp -i "${KEY_NAME}.pem" \
        deployment/aws-ubuntu/.env.production \
        ubuntu@"$PUBLIC_IP":/opt/canvas-scraper/.env
    
    scp -i "${KEY_NAME}.pem" \
        deployment/aws-ubuntu/courses.yml \
        ubuntu@"$PUBLIC_IP":/opt/canvas-scraper/config/
    
    # Create docker-compose.yml on remote server
    ssh -i "${KEY_NAME}.pem" ubuntu@"$PUBLIC_IP" << 'REMOTE_DOCKER_COMPOSE'
cat > /opt/canvas-scraper/docker-compose.yml << 'EOF'
version: '3.8'

services:
  canvas-scraper:
    build: 
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: canvas-scraper-enhanced
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - PYTHONPATH=/app
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
      - ENABLE_HEALTH_SERVER=true
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
      - ./downloads:/app/downloads
    ports:
      - "8080:8080"
    networks:
      - canvas-network
    healthcheck:
      test: ["CMD", "python", "/healthcheck.py"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  canvas-network:
    driver: bridge
EOF
REMOTE_DOCKER_COMPOSE
    
    # Build and start container on remote server
    log_info "Building and starting container on remote server..."
    ssh -i "${KEY_NAME}.pem" ubuntu@"$PUBLIC_IP" << 'REMOTE_START'
        cd /opt/canvas-scraper
        
        # Wait for Docker to be ready
        while ! docker info > /dev/null 2>&1; do
            echo "Waiting for Docker to start..."
            sleep 5
        done
        
        # Build and start
        docker compose build
        docker compose up -d
        
        # Check status
        sleep 10
        docker compose ps
REMOTE_START
    
    log_success "Deployment completed successfully!"
}

print_summary() {
    echo ""
    log_success "Deployment Summary:"
    echo "  Instance ID: $INSTANCE_ID"
    echo "  Public IP: $PUBLIC_IP"
    echo "  SSH Command: ssh -i ${KEY_NAME}.pem ubuntu@$PUBLIC_IP"
    echo "  Health Check: http://$PUBLIC_IP:8080/health"
    echo "  Application Directory: /opt/canvas-scraper"
    echo ""
    log_info "Next steps:"
    echo "  1. Update .env.production with your Canvas API credentials"
    echo "  2. Update courses.yml with your course IDs"
    echo "  3. Restart the service: docker compose restart"
    echo "  4. Monitor logs: docker compose logs -f canvas-scraper"
    echo ""
    log_info "Management commands:"
    echo "  - Check status: docker compose ps"
    echo "  - View logs: docker compose logs -f"
    echo "  - Restart: docker compose restart"
    echo "  - Stop: docker compose down"
    echo ""
}

# Main execution
main() {
    echo "Canvas Scraper Enhanced - AWS Ubuntu Deployment"
    echo "================================================"
    
    check_prerequisites
    setup_environment
    build_docker_image
    create_key_pair
    create_security_group
    launch_instance
    deploy_to_instance
    print_summary
}

# Run main function
main "$@"