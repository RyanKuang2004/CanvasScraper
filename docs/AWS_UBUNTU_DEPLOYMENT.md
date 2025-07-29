# AWS Ubuntu Deployment Guide - Canvas Scraper Enhanced

Complete deployment guide for running Canvas Scraper Enhanced Docker container on AWS Ubuntu instances.

## Prerequisites

- AWS account with configured CLI credentials
- Canvas API credentials
- Optional: Supabase project for enhanced storage
- Basic familiarity with Docker and Ubuntu

---

## Table of Contents

1. [Local Preparation](#1-local-preparation)
2. [AWS Infrastructure Setup](#2-aws-infrastructure-setup)
3. [EC2 Instance Configuration](#3-ec2-instance-configuration)
4. [Docker Container Deployment](#4-docker-container-deployment)
5. [Environment Configuration](#5-environment-configuration)
6. [Service Management](#6-service-management)
7. [Monitoring & Maintenance](#7-monitoring--maintenance)
8. [Scaling & Optimization](#8-scaling--optimization)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Local Preparation

### 1.1 Build and Test Docker Image

```bash
# Clone and navigate to project
git clone <your-canvas-scraper-repo>
cd CanvasScraper

# Test the application locally first
python3 tests/test_docker_standalone.py

# Build Docker image
docker build -t canvas-scraper-enhanced .

# Test the container locally
docker run --rm -it \
  -e CANVAS_API_TOKEN="your_token" \
  -e CANVAS_URL="https://your-canvas-instance.edu/api/v1" \
  canvas-scraper-enhanced

# Tag for AWS deployment
docker tag canvas-scraper-enhanced:latest your-registry/canvas-scraper:v2.0
```

### 1.2 Prepare Configuration Files

Create deployment configuration:

```bash
# Create deployment directory
mkdir -p deployment/aws-ubuntu
cd deployment/aws-ubuntu

# Create environment file
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
CRON_SCHEDULE=0 2,14 * * *  # Run at 2 AM and 2 PM daily
EOF

# Create courses configuration
cat > courses.yml << 'EOF'
# Canvas Course Configuration for Production
enabled_courses:
  - "12345"  # Replace with your actual course IDs
  - "67890"
  - "11111"

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
    - "12:00"  # 12 PM
    - "20:00"  # 8 PM

deduplication:
  enabled: true
  check_content_changes: true
  fingerprint_algorithm: "sha256"
EOF
```

---

## 2. AWS Infrastructure Setup

### 2.1 Launch EC2 Instance

```bash
# Create key pair (if you don't have one)
aws ec2 create-key-pair \
  --key-name canvas-scraper-key \
  --query 'KeyMaterial' \
  --output text > canvas-scraper-key.pem
chmod 400 canvas-scraper-key.pem

# Create security group
aws ec2 create-security-group \
  --group-name canvas-scraper-sg \
  --description "Security group for Canvas Scraper"

# Get security group ID
SG_ID=$(aws ec2 describe-security-groups \
  --group-names canvas-scraper-sg \
  --query 'SecurityGroups[0].GroupId' \
  --output text)

# Add SSH access (replace YOUR_IP with your IP address)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32

# Add health check port
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8080 \
  --cidr 0.0.0.0/0

# Launch Ubuntu instance
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --count 1 \
  --instance-type t3.medium \
  --key-name canvas-scraper-key \
  --security-group-ids $SG_ID \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=canvas-scraper-production}]' \
  --user-data '#!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu'
```

### 2.2 Get Instance Information

```bash
# Get instance ID and public IP
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=canvas-scraper-production" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
```

---

## 3. EC2 Instance Configuration

### 3.1 Connect to Instance

```bash
# Connect via SSH
ssh -i canvas-scraper-key.pem ubuntu@$PUBLIC_IP
```

### 3.2 Install Required Software

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose
sudo apt install -y docker.io docker-compose-plugin curl wget unzip

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Log out and back in for group changes to take effect
exit
ssh -i canvas-scraper-key.pem ubuntu@$PUBLIC_IP

# Verify Docker installation
docker --version
docker compose version
```

### 3.3 Create Application Directory Structure

```bash
# Create application directories
sudo mkdir -p /opt/canvas-scraper/{config,logs,data,downloads}

# Set ownership
sudo chown -R ubuntu:ubuntu /opt/canvas-scraper

# Create systemd service directory
sudo mkdir -p /etc/systemd/system
```

---

## 4. Docker Container Deployment

### 4.1 Transfer Files to Server

From your local machine:

```bash
# Copy configuration files
scp -i canvas-scraper-key.pem .env.production ubuntu@$PUBLIC_IP:/opt/canvas-scraper/.env
scp -i canvas-scraper-key.pem courses.yml ubuntu@$PUBLIC_IP:/opt/canvas-scraper/config/

# Alternative: Clone repository directly on server
ssh -i canvas-scraper-key.pem ubuntu@$PUBLIC_IP
cd /opt/canvas-scraper
git clone <your-repo-url> source
cd source
```

### 4.2 Create Docker Compose Configuration

```bash
# Create docker-compose.yml
cat > /opt/canvas-scraper/docker-compose.yml << 'EOF'
version: '3.8'

services:
  canvas-scraper:
    build: 
      context: ./source
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
      - "8080:8080"  # Health check endpoint
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

volumes:
  canvas-data:
    driver: local
EOF
```

### 4.3 Build and Start Container

```bash
cd /opt/canvas-scraper

# Build the container
docker compose build

# Start in detached mode
docker compose up -d

# Check status
docker compose ps
docker compose logs -f canvas-scraper
```

---

## 5. Environment Configuration

### 5.1 Configure Systemd Service

```bash
# Create systemd service file
sudo cat > /etc/systemd/system/canvas-scraper.service << 'EOF'
[Unit]
Description=Canvas Scraper Enhanced Docker Container
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/canvas-scraper
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart
TimeoutStartSec=0
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable canvas-scraper.service
```

### 5.2 Configure Log Rotation

```bash
# Create logrotate configuration
sudo cat > /etc/logrotate.d/canvas-scraper << 'EOF'
/opt/canvas-scraper/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
    postrotate
        /usr/bin/docker compose -f /opt/canvas-scraper/docker-compose.yml restart canvas-scraper > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 5.3 Configure Firewall (UFW)

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow health check port
sudo ufw allow 8080/tcp

# Check status
sudo ufw status
```

---

## 6. Service Management

### 6.1 Basic Service Commands

```bash
# Start service
sudo systemctl start canvas-scraper

# Stop service
sudo systemctl stop canvas-scraper

# Restart service
sudo systemctl restart canvas-scraper

# Check service status
sudo systemctl status canvas-scraper

# View logs
sudo journalctl -u canvas-scraper -f

# View application logs
docker compose logs -f canvas-scraper
```

### 6.2 Health Monitoring

```bash
# Check container health
docker compose ps
curl http://localhost:8080/health

# Monitor resource usage
docker stats canvas-scraper-enhanced

# Check disk usage
df -h /opt/canvas-scraper
```

### 6.3 Application Management

```bash
# Run one-time scraping
docker compose exec canvas-scraper python scripts/run_enhanced_scraper.py run

# Search processed content
docker compose exec canvas-scraper python scripts/run_enhanced_scraper.py search --query "machine learning"

# View processing statistics
docker compose exec canvas-scraper python scripts/run_enhanced_scraper.py stats

# Access container shell
docker compose exec canvas-scraper bash
```

---

## 7. Monitoring & Maintenance

### 7.1 Automated Monitoring Script

```bash
# Create monitoring script
cat > /opt/canvas-scraper/monitor.sh << 'EOF'
#!/bin/bash

LOG_FILE="/opt/canvas-scraper/logs/monitor.log"
HEALTH_URL="http://localhost:8080/health"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check container health
if ! curl -s "$HEALTH_URL" > /dev/null; then
    log "ALERT: Health check failed"
    # Restart container
    cd /opt/canvas-scraper
    docker compose restart canvas-scraper
    log "Container restarted"
else
    log "Health check passed"
fi

# Check disk space
DISK_USAGE=$(df /opt/canvas-scraper | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    log "WARNING: Disk usage at ${DISK_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(docker stats --no-stream --format "table {{.MemPerc}}" canvas-scraper-enhanced | tail -1 | sed 's/%//')
if [ "${MEMORY_USAGE%.*}" -gt 80 ]; then
    log "WARNING: Memory usage at ${MEMORY_USAGE}%"
fi
EOF

chmod +x /opt/canvas-scraper/monitor.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/canvas-scraper/monitor.sh") | crontab -
```

### 7.2 Backup Strategy

```bash
# Create backup script
cat > /opt/canvas-scraper/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/opt/canvas-scraper/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup configuration and data
tar -czf "$BACKUP_DIR/canvas-scraper-backup-$DATE.tar.gz" \
    -C /opt/canvas-scraper \
    config data logs \
    --exclude='*.tmp' \
    --exclude='downloads/*'

# Keep only last 7 backups
find "$BACKUP_DIR" -name "canvas-scraper-backup-*.tar.gz" -mtime +7 -delete

echo "Backup completed: canvas-scraper-backup-$DATE.tar.gz"
EOF

chmod +x /opt/canvas-scraper/backup.sh

# Schedule daily backups
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/canvas-scraper/backup.sh") | crontab -
```

### 7.3 Update Process

```bash
# Create update script
cat > /opt/canvas-scraper/update.sh << 'EOF'
#!/bin/bash

cd /opt/canvas-scraper/source

# Pull latest changes
git pull origin main

# Rebuild container
cd /opt/canvas-scraper
docker compose build --no-cache

# Restart with new image
docker compose up -d

echo "Update completed"
EOF

chmod +x /opt/canvas-scraper/update.sh
```

---

## 8. Scaling & Optimization

### 8.1 Instance Sizing Recommendations

| Use Case | Instance Type | CPU | Memory | Storage | Monthly Cost* |
|----------|---------------|-----|---------|---------|---------------|
| Small (1-5 courses) | t3.micro | 2 vCPU | 1 GB | 20 GB | ~$10 |
| Medium (5-20 courses) | t3.small | 2 vCPU | 2 GB | 30 GB | ~$20 |
| Large (20+ courses) | t3.medium | 2 vCPU | 4 GB | 50 GB | ~$35 |
| Heavy processing | t3.large | 2 vCPU | 8 GB | 100 GB | ~$75 |

*Approximate costs, check current AWS pricing

### 8.2 Performance Optimization

```bash
# Optimize Docker settings
cat > /opt/canvas-scraper/docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  canvas-scraper:
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 3G
        reservations:
          cpus: '0.5'
          memory: 1G
    environment:
      - CONCURRENT_DOWNLOADS=5  # Increase for larger instances
      - MAX_FILE_SIZE_MB=100    # Adjust based on needs
EOF
```

### 8.3 Auto Scaling with CloudWatch

```bash
# Create CloudWatch alarm for high CPU
aws cloudwatch put-metric-alarm \
  --alarm-name "canvas-scraper-high-cpu" \
  --alarm-description "High CPU utilization" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=InstanceId,Value=$INSTANCE_ID \
  --evaluation-periods 2
```

---

## 9. Troubleshooting

### 9.1 Common Issues

**Container won't start:**
```bash
# Check logs
docker compose logs canvas-scraper

# Check configuration
docker compose config

# Validate environment variables
docker compose exec canvas-scraper env | grep CANVAS
```

**High memory usage:**
```bash
# Check memory stats
docker stats canvas-scraper-enhanced

# Restart container
docker compose restart canvas-scraper

# Check for memory leaks
docker compose exec canvas-scraper python scripts/run_enhanced_scraper.py stats
```

**Canvas API connection issues:**
```bash
# Test API connection
docker compose exec canvas-scraper curl -H "Authorization: Bearer $CANVAS_API_TOKEN" $CANVAS_URL/users/self

# Check network connectivity
docker compose exec canvas-scraper ping -c 3 canvas.lms.unimelb.edu.au
```

### 9.2 Log Analysis

```bash
# View recent application logs
tail -f /opt/canvas-scraper/logs/canvas_scraper.log

# Search for errors
grep -i error /opt/canvas-scraper/logs/*.log

# Monitor real-time processing
docker compose logs -f canvas-scraper | grep -E "(Processing|Error|Complete)"
```

### 9.3 Emergency Recovery

```bash
# Quick restart
sudo systemctl restart canvas-scraper

# Full container rebuild
cd /opt/canvas-scraper
docker compose down
docker compose build --no-cache
docker compose up -d

# Restore from backup
cd /opt/canvas-scraper/backups
tar -xzf canvas-scraper-backup-YYYYMMDD_HHMMSS.tar.gz -C /opt/canvas-scraper/
```

---

## 10. Production Checklist

### Pre-Deployment
- [ ] Canvas API credentials tested
- [ ] Supabase project configured (if using)
- [ ] Course IDs verified in courses.yml
- [ ] Docker image builds successfully
- [ ] Local tests pass
- [ ] Backup strategy in place

### Post-Deployment
- [ ] Container health check passes
- [ ] Scheduled jobs configured
- [ ] Monitoring scripts active
- [ ] Log rotation configured
- [ ] Firewall rules applied
- [ ] SSL/TLS configured (if needed)
- [ ] Backup tested and verified

### Ongoing Maintenance
- [ ] Weekly log review
- [ ] Monthly backup verification
- [ ] Quarterly security updates
- [ ] Performance monitoring
- [ ] Cost optimization review

---

## Security Considerations

1. **Secure API Keys**: Store in environment variables, never in code
2. **Network Security**: Use security groups to restrict access
3. **Regular Updates**: Keep Ubuntu, Docker, and application updated
4. **Access Control**: Use IAM roles and SSH key authentication
5. **Monitoring**: Set up CloudWatch alarms for anomalous activity
6. **Backup Encryption**: Encrypt backups if they contain sensitive data

---

## Support & Resources

- **Application Logs**: `/opt/canvas-scraper/logs/`
- **Configuration**: `/opt/canvas-scraper/config/`
- **Health Check**: `http://YOUR_IP:8080/health`
- **AWS Documentation**: [EC2 User Guide](https://docs.aws.amazon.com/ec2/)
- **Docker Documentation**: [Docker Compose](https://docs.docker.com/compose/)

For additional support, check the project repository issues or create a new issue with deployment logs and configuration details.