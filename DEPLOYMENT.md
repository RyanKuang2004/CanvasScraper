# Canvas Scraper - AWS EC2 Deployment Guide

This guide provides comprehensive instructions for deploying the Canvas Scraper application to AWS EC2 using Docker containers.

## 🏗️ Architecture Overview

### Infrastructure Components
- **VPC**: Isolated network environment with public subnet
- **EC2 Instance**: t3.micro instance running Amazon Linux 2
- **Security Groups**: Restricted access (SSH from your IP only)
- **IAM Role**: Minimal permissions for CloudWatch and SSM
- **SSM Parameter Store**: Secure storage for Canvas API token
- **CloudWatch**: Comprehensive logging and monitoring

### Application Stack
- **Docker**: Containerized Python application
- **Python 3.11**: Latest stable Python runtime
- **Async HTTP**: aiohttp for Canvas API interactions
- **Health Monitoring**: Built-in health checks and monitoring

## 🚀 Quick Start Deployment

### Prerequisites
1. **AWS CLI**: Installed and configured with appropriate permissions
2. **Docker**: Installed locally for testing
3. **Canvas API Token**: Valid token from your Canvas instance

### One-Command Deployment
```bash
cd deploy
export CANVAS_API_TOKEN="your_canvas_token_here"
./deploy.sh canvas-scraper us-east-1
```

This script will:
- ✅ Create EC2 key pair for SSH access
- ✅ Deploy CloudFormation infrastructure stack
- ✅ Install Docker and dependencies on EC2
- ✅ Build and run the Canvas Scraper container
- ✅ Configure monitoring and logging

## 📁 Project Structure

```
CanvasScraper/
├── aws/                          # AWS Infrastructure
│   └── cloudformation.yml        # Complete infrastructure as code
├── deploy/                       # Deployment scripts
│   └── deploy.sh                 # Automated deployment script
├── monitoring/                   # Monitoring and health checks
│   ├── cloudwatch-config.json   # CloudWatch agent configuration
│   └── health_check.py          # Application health monitoring
├── security/                     # Security specifications
│   └── security-config.yml      # Security requirements and compliance
├── .github/workflows/            # CI/CD Pipeline
│   └── deploy.yml               # GitHub Actions workflow
├── Dockerfile                    # Multi-stage container build
├── docker-compose.yml           # Local development and deployment
├── .dockerignore                # Docker build optimization
└── DEPLOYMENT.md                # This file
```

## 🔧 Manual Deployment Steps

### 1. Infrastructure Deployment
```bash
# Deploy CloudFormation stack
aws cloudformation deploy \
    --template-file aws/cloudformation.yml \
    --stack-name canvas-scraper-infrastructure \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        EnvironmentName=canvas-scraper \
        KeyPairName=canvas-scraper-keypair \
        CanvasAPIToken="your_token_here"
```

### 2. Application Deployment
```bash
# Get instance IP
INSTANCE_IP=$(aws cloudformation describe-stacks \
    --stack-name canvas-scraper-infrastructure \
    --query 'Stacks[0].Outputs[?OutputKey==`InstancePublicIP`].OutputValue' \
    --output text)

# SSH to instance
ssh -i ~/.ssh/canvas-scraper-keypair.pem ec2-user@$INSTANCE_IP

# On the instance:
cd ~/canvas-scraper
sudo docker-compose up -d
```

## 🔐 Security Features

### Network Security
- **VPC Isolation**: Dedicated VPC with controlled network access
- **Security Groups**: SSH access restricted to deployment IP only
- **No Public Ports**: Application runs internally, no external exposure

### Data Security
- **Encrypted Secrets**: Canvas API token stored in AWS SSM Parameter Store
- **TLS Communication**: All API calls use HTTPS/TLS 1.2+
- **EBS Encryption**: Storage volumes encrypted at rest

### Container Security
- **Non-Root User**: Application runs as unprivileged user (uid 1000)
- **Resource Limits**: Memory and CPU constraints prevent resource exhaustion
- **Multi-Stage Build**: Minimal attack surface with optimized layers

### Access Control
- **IAM Roles**: Least-privilege access with specific permissions
- **Key-Based SSH**: No password authentication, key pairs only
- **Audit Logging**: All actions logged to CloudWatch for compliance

## 📊 Monitoring & Observability

### CloudWatch Integration
- **System Metrics**: CPU, memory, disk, network utilization
- **Application Logs**: Centralized logging with retention policies
- **Health Checks**: Built-in health monitoring with Docker health checks

### Alerting
```bash
# Example: Create CloudWatch alarm for high CPU usage
aws cloudwatch put-metric-alarm \
    --alarm-name "CanvasScraper-HighCPU" \
    --alarm-description "Canvas Scraper High CPU Usage" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2
```

### Health Check Endpoint
```bash
# Manual health check
python monitoring/health_check.py

# Expected output:
{
  "timestamp": "2024-01-20T10:30:00Z",
  "overall_status": "healthy",
  "uptime_seconds": 3600.0,
  "checks": {
    "config": {"status": "healthy"},
    "canvas_api": {"status": "healthy"},
    "system_resources": {"status": "healthy"}
  }
}
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow
The project includes a complete CI/CD pipeline that:

1. **Testing**: Runs pytest suite and code quality checks
2. **Security**: Performs vulnerability scanning with Trivy
3. **Building**: Creates optimized Docker images
4. **Deployment**: Automated deployment to staging/production
5. **Monitoring**: Post-deployment health verification

### Required Secrets
Set these in your GitHub repository settings:
```bash
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
CANVAS_API_TOKEN_STAGING=staging_canvas_token
CANVAS_API_TOKEN_PRODUCTION=production_canvas_token
```

### Deployment Triggers
- **Staging**: Pushes to `develop` branch
- **Production**: Git tags starting with `v` (e.g., `v1.0.0`)
- **Manual**: Workflow dispatch with environment selection

## 🛠️ Operations

### Application Management
```bash
# Check application status
sudo docker-compose ps

# View application logs
sudo docker-compose logs -f

# Restart application
sudo docker-compose restart

# Update application
git pull origin main
sudo docker-compose up -d --build
```

### Backup and Recovery
```bash
# Create EBS snapshot
aws ec2 create-snapshot \
    --volume-id vol-xxxxxxxxx \
    --description "Canvas Scraper Backup $(date)"

# List available snapshots
aws ec2 describe-snapshots \
    --owner-ids self \
    --filters "Name=description,Values=Canvas Scraper Backup*"
```

### Scaling Considerations
- **Vertical Scaling**: Upgrade instance type in CloudFormation template
- **Horizontal Scaling**: Deploy additional instances with load balancer
- **Auto Scaling**: Implement Auto Scaling Groups for automated scaling

## 🚨 Troubleshooting

### Common Issues

#### 1. SSH Connection Failed
```bash
# Check security group allows your current IP
aws ec2 describe-security-groups \
    --group-ids sg-xxxxxxxxx \
    --query 'SecurityGroups[0].IpPermissions'

# Update security group if needed
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxxx \
    --protocol tcp \
    --port 22 \
    --cidr $(curl -s https://checkip.amazonaws.com/)/32
```

#### 2. Docker Container Not Starting
```bash
# Check Docker service status
sudo systemctl status docker

# Check container logs
sudo docker-compose logs canvas-scraper

# Restart Docker service
sudo systemctl restart docker
```

#### 3. Canvas API Authentication Errors
```bash
# Verify token in SSM Parameter Store
aws ssm get-parameter \
    --name /canvas-scraper/canvas-api-token \
    --with-decryption \
    --query Parameter.Value \
    --output text

# Test API connectivity
curl -H "Authorization: Bearer YOUR_TOKEN" \
    https://canvas.lms.unimelb.edu.au/api/v1/users/self
```

### Performance Tuning
```bash
# Monitor resource usage
htop

# Check application performance
sudo docker stats

# Optimize Docker resources
sudo docker system prune -a
```

## 💰 Cost Optimization

### Instance Sizing
- **Development**: t3.micro (1 vCPU, 1GB RAM) - ~$8.50/month
- **Production**: t3.small (2 vCPU, 2GB RAM) - ~$17/month

### Cost Monitoring
```bash
# Enable cost allocation tags
aws ce put-dimension-key \
    --key Environment \
    --type COST_CATEGORY
```

## 📞 Support

### Resources
- **AWS Documentation**: https://docs.aws.amazon.com/
- **Docker Documentation**: https://docs.docker.com/
- **Canvas API Documentation**: https://canvas.instructure.com/doc/api/

### Getting Help
1. Check CloudWatch logs for error details
2. Run health check script for diagnostics
3. Review security group and IAM configurations
4. Consult AWS support for infrastructure issues

---

**Deployment completed successfully!** 🎉

Your Canvas Scraper is now running securely in AWS with comprehensive monitoring and automated deployment capabilities.