# Canvas Scraper Docker Deployment Guide

This directory contains production-ready Docker deployment configurations for the Canvas Scraper application.

## 🏗️ Architecture Overview

### Multi-Stage Dockerfile Design
- **Builder Stage**: Compiles dependencies and creates optimized virtual environment
- **Production Stage**: Minimal runtime with security hardening and health checks
- **Development Stage**: Extended with dev tools for local development

### Key Features
- ✅ **Security Hardened**: Non-root user, minimal attack surface
- ✅ **Health Monitoring**: Built-in health checks and monitoring endpoints
- ✅ **Production Ready**: Resource limits, logging, restart policies
- ✅ **Multi-Platform**: Supports AMD64 and ARM64 architectures
- ✅ **CI/CD Integrated**: GitHub Actions workflows included

## 🚀 Quick Start

### 1. Simple Deployment
```bash
# Copy environment configuration
cp docker/.env.docker .env
# Edit .env with your Canvas API token

# Build and run
docker build -t canvas-scraper .
docker run -d --name canvas-scraper \
  --env-file .env \
  -v canvas_logs:/app/logs \
  -v canvas_data:/app/data \
  -p 8080:8080 \
  canvas-scraper
```

### 2. Docker Compose (Recommended)
```bash
# Development environment
docker-compose up -d

# Production with database
docker-compose --profile database up -d

# Full stack with monitoring
docker-compose -f docker/docker-compose.prod.yml \
  --profile monitoring --profile logging up -d
```

### 3. Production Deployment Script
```bash
# Automated production deployment
chmod +x docker/docker-deploy.sh

# Deploy with blue-green strategy
DEPLOYMENT_TYPE=blue-green ./docker/docker-deploy.sh deploy

# Rolling deployment (faster)
./docker/docker-deploy.sh deploy

# Check status
./docker/docker-deploy.sh status

# View logs
./docker/docker-deploy.sh logs
```

## 📁 File Structure

```
docker/
├── entrypoint.sh              # Container initialization script
├── healthcheck.py             # Health monitoring script
├── docker-deploy.sh           # Production deployment automation
├── docker-compose.prod.yml    # Production compose configuration
├── .env.docker                # Environment template
└── README.md                  # This documentation
```

## ⚙️ Configuration Options

### Environment Variables

#### Required
- `CANVAS_API_TOKEN`: Your Canvas API access token
- `CANVAS_URL`: Canvas API endpoint

#### Optional Features
- `ENABLE_CRON=true`: Enable scheduled execution
- `CRON_SCHEDULE="0 2 * * *"`: Cron schedule (default: 2 AM daily)
- `ENABLE_HEALTH_SERVER=true`: Enable health check endpoint
- `LOG_LEVEL=INFO`: Logging verbosity

#### Database Integration
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_KEY`: Supabase service key

### Docker Compose Profiles

| Profile | Purpose | Services |
|---------|---------|----------|
| default | Basic scraper | canvas-scraper |
| database | With PostgreSQL | + postgres, redis |
| development | Dev environment | + dev tools, code mounting |
| monitoring | Observability | + prometheus, grafana |
| logging | Log aggregation | + elasticsearch, kibana |
| proxy | Reverse proxy | + nginx |

## 🔧 Deployment Strategies

### 1. Rolling Deployment (Default)
- **Speed**: Fast deployment
- **Downtime**: Brief interruption
- **Rollback**: Manual process
- **Use Case**: Development, staging

```bash
./docker/docker-deploy.sh deploy
```

### 2. Blue-Green Deployment
- **Speed**: Slower but safer
- **Downtime**: Zero downtime
- **Rollback**: Automated
- **Use Case**: Production

```bash
DEPLOYMENT_TYPE=blue-green ./docker/docker-deploy.sh deploy
```

### 3. Canary Deployment (Manual)
```bash
# Deploy to subset of instances
docker run -d --name canvas-scraper-canary \
  --env-file .env \
  -p 8081:8080 \
  canvas-scraper:latest

# Monitor and promote if successful
```

## 📊 Monitoring & Observability

### Health Checks
- **Container Health**: Built-in Docker health checks
- **Application Health**: `/health` endpoint on port 8080
- **Custom Checks**: Environment, dependencies, Canvas connectivity

### Logging
- **Application Logs**: Structured JSON logging to `/app/logs`
- **Container Logs**: Docker logging drivers with rotation
- **Centralized Logging**: Optional ELK stack integration

### Metrics (Optional)
- **Prometheus**: Application and system metrics
- **Grafana**: Visualization dashboards
- **Alerts**: Configurable alerting rules

## 🛡️ Security Features

### Container Security
- **Non-root User**: Runs as `canvas:canvas` user
- **Read-only Filesystem**: Minimal write permissions
- **Security Options**: `no-new-privileges`
- **Vulnerability Scanning**: Trivy integration

### Network Security
- **Isolated Networks**: Custom Docker networks
- **Port Restrictions**: Only necessary ports exposed
- **SSL/TLS**: Optional NGINX reverse proxy with SSL

### Secrets Management
- **Environment Files**: Secure credential storage
- **Docker Secrets**: Production secrets management
- **Runtime Security**: No hardcoded credentials

## 🔄 CI/CD Integration

### GitHub Actions Workflow
- **Automated Testing**: Multi-Python version testing
- **Security Scanning**: Trivy vulnerability scans
- **Multi-Platform Builds**: AMD64 and ARM64 support
- **Automated Deployment**: Staging and production pipelines

### Deployment Triggers
- **Develop Branch**: Auto-deploy to staging
- **Version Tags**: Auto-deploy to production
- **Manual Triggers**: Environment-specific deployments

## 🚨 Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check logs
docker logs canvas-scraper

# Validate health
docker exec canvas-scraper python /healthcheck.py

# Check environment
docker exec canvas-scraper env | grep CANVAS
```

#### Health Check Failures
```bash
# Manual health check
docker exec canvas-scraper python /healthcheck.py

# Check Canvas connectivity
docker exec canvas-scraper curl -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_URL/courses"
```

#### Performance Issues
```bash
# Check resource usage
docker stats canvas-scraper

# Review logs
docker logs --tail 100 canvas-scraper

# Monitor health endpoint
curl http://localhost:8080/health
```

### Recovery Procedures

#### Rollback Deployment
```bash
# Automatic rollback
./docker/docker-deploy.sh rollback

# Manual rollback to specific version
docker stop canvas-scraper
docker run -d --name canvas-scraper \
  --env-file .env \
  canvas-scraper:v1.0.0
```

#### Emergency Stop
```bash
# Stop all related containers
docker-compose down

# Force removal
docker stop canvas-scraper && docker rm canvas-scraper
```

## 📈 Performance Optimization

### Resource Allocation
```yaml
deploy:
  resources:
    limits:
      memory: 512M      # Adjust based on requirements
      cpus: '1.0'
    reservations:
      memory: 256M
      cpus: '0.5'
```

### Volume Optimization
- **Logs**: Use log rotation and external log management
- **Data**: Consider object storage for large datasets
- **Cache**: Implement Redis for API response caching

### Network Performance
- **HTTP/2**: Enable in reverse proxy
- **Connection Pooling**: aiohttp connection management
- **DNS Caching**: Container-level DNS optimization

## 🔧 Advanced Configuration

### Custom Health Checks
Edit `docker/healthcheck.py` to add application-specific health validations.

### Environment-Specific Overrides
Create environment-specific compose files:
```bash
# staging
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up

# production
docker-compose -f docker/docker-compose.prod.yml up
```

### Resource Monitoring
```bash
# Enable monitoring stack
docker-compose --profile monitoring up -d

# Access Grafana: http://localhost:3000
# Access Prometheus: http://localhost:9090
```

---

## 📞 Support

For deployment issues:
1. Check container logs: `docker logs canvas-scraper`
2. Run health check: `docker exec canvas-scraper python /healthcheck.py`
3. Review environment configuration
4. Consult main project documentation

**Production Ready** ✅ | **Security Hardened** 🛡️ | **CI/CD Integrated** 🔄