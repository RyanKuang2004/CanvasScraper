# Docker Compose Guide - Canvas Scraper Enhanced v2.0

Complete guide for using the updated Docker Compose configuration with Canvas Scraper Enhanced v2.0.

## 📁 Docker Compose Files

### Core Files
- **`docker-compose.yml`** - Main configuration with all services and profiles
- **`docker-compose.production.yml`** - Production overrides with monitoring
- **`docker-compose.aws.yml`** - AWS-optimized configuration
- **`.env.example`** - Environment variables template

## 🚀 Quick Start

### 1. Basic Setup
```bash
# Copy environment template
cp .env.example .env

# Edit with your Canvas API credentials
nano .env

# Create required directories
mkdir -p logs data downloads config

# Copy sample configuration
cp config/courses.yml.example config/courses.yml
```

### 2. Production Deployment (Default)
```bash
# Standard production deployment
docker compose up -d

# Check status
docker compose ps
docker compose logs -f canvas-scraper
```

### 3. AWS Deployment
```bash
# AWS-optimized deployment
docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d

# Check health
curl http://localhost:8080/health
```

## 🔧 Service Profiles

### Available Profiles
The configuration uses Docker Compose profiles to organize different service combinations:

| Profile | Services | Use Case |
|---------|----------|----------|
| `default` | canvas-scraper | Production deployment |
| `development` | canvas-scraper-dev | Live development |
| `database` | postgres | Legacy PostgreSQL |
| `supabase` | supabase-db | Local Supabase development |
| `queue` | redis | Job queue processing |
| `monitoring` | prometheus, grafana | Production monitoring |

### Profile Usage Examples

```bash
# Development with live code mounting
docker compose --profile development up -d

# Production with PostgreSQL database
docker compose --profile database up -d

# Production with Supabase local development
docker compose --profile supabase up -d

# Full stack with monitoring
docker compose --profile database --profile monitoring up -d

# Development with all services
docker compose --profile development --profile database --profile queue up -d
```

## 🌟 Enhanced v2.0 Features

### Configuration Management
- **YAML Configuration**: `./config/courses.yml` for course selection
- **Environment Variables**: Complete `.env` support
- **Volume Mounting**: Persistent data and configuration

### Improved Volumes
```yaml
volumes:
  - ./config:/app/config:ro     # YAML configuration files
  - ./logs:/app/logs            # Application logs
  - ./data:/app/data            # Processed data storage
  - ./downloads:/app/downloads  # Temporary file downloads
```

### Enhanced Scheduling
- **Cron Integration**: Built-in scheduling with `ENABLE_CRON=true`
- **Melbourne Timezone**: Automatic timezone handling
- **Configurable Schedule**: Custom cron expressions via `CRON_SCHEDULE`

### Supabase Integration
- **Cloud Integration**: Direct Supabase cloud connection
- **Local Development**: Optional local Supabase instance
- **Fallback Support**: Graceful operation without Supabase

## 📊 Monitoring & Health Checks

### Health Endpoints
```bash
# Check application health
curl http://localhost:8080/health

# Development instance (if running)
curl http://localhost:8081/health
```

### Log Monitoring
```bash
# View real-time logs
docker compose logs -f canvas-scraper

# View specific service logs
docker compose logs -f postgres
docker compose logs -f redis

# View all services
docker compose logs -f
```

### Resource Monitoring
```bash
# Check container resource usage
docker stats canvas-scraper-enhanced

# View container details
docker compose ps
docker inspect canvas-scraper-enhanced
```

## 🛠️ Management Commands

### Service Management
```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# Restart specific service
docker compose restart canvas-scraper

# Rebuild and restart
docker compose up -d --build

# View service status
docker compose ps
```

### Data Management
```bash
# Backup data volumes
docker run --rm -v $(pwd)/data:/backup-source -v $(pwd)/backups:/backup-dest alpine tar czf /backup-dest/data-$(date +%Y%m%d).tar.gz -C /backup-source .

# Clean up downloads
docker compose exec canvas-scraper rm -rf /app/downloads/*

# View disk usage
docker system df
docker compose exec canvas-scraper df -h
```

### Application Commands
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

## 🔧 Configuration Examples

### Environment Variables (.env)
```bash
# Canvas API Configuration
CANVAS_API_TOKEN=your_actual_token_here
CANVAS_URL=https://canvas.lms.unimelb.edu.au/api/v1

# Supabase Integration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key

# Processing Configuration
CONCURRENT_DOWNLOADS=5
MAX_FILE_SIZE_MB=100
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Scheduling
ENABLE_CRON=true
CRON_SCHEDULE=0 2,14 * * *  # 2 AM and 2 PM daily
```

### Course Configuration (config/courses.yml)
```yaml
enabled_courses:
  - "12345"
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
    - "12:00"
    - "20:00"

deduplication:
  enabled: true
  check_content_changes: true
  fingerprint_algorithm: "sha256"
```

## 🚀 Deployment Scenarios

### Local Development
```bash
# Development with live code mounting
docker compose --profile development up -d

# Access development instance
curl http://localhost:8081/health
docker compose logs -f canvas-dev
```

### Production Deployment
```bash
# Standard production
docker compose up -d

# Production with monitoring
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d

# Access monitoring
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### AWS Deployment
```bash
# AWS-optimized deployment
docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d

# Verify deployment
curl http://your-ec2-ip:8080/health
docker compose logs -f canvas-scraper
```

### Scaling Configuration
```yaml
# For larger instances, create docker-compose.override.yml
services:
  canvas-scraper:
    environment:
      - CONCURRENT_DOWNLOADS=10
      - MAX_FILE_SIZE_MB=200
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
```

## 🔒 Security Considerations

### Environment Security
- Store sensitive credentials in `.env` files
- Use Docker secrets for production deployments
- Regularly rotate API tokens and passwords
- Restrict network access using Docker networks

### Container Security
- Run containers as non-root users
- Use specific Docker image tags, not `latest`
- Regularly update base images
- Scan images for vulnerabilities

### Data Security
- Encrypt sensitive data at rest
- Use secure communication protocols
- Implement proper backup strategies
- Monitor access logs and authentication

## 🔧 Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker compose logs canvas-scraper

# Validate configuration
docker compose config

# Check environment variables
docker compose exec canvas-scraper env | grep CANVAS
```

**Permission errors:**
```bash
# Fix volume permissions
sudo chown -R 1000:1000 logs data downloads config
chmod -R 755 logs data downloads config
```

**Network connectivity:**
```bash
# Test Canvas API connection
docker compose exec canvas-scraper curl -H "Authorization: Bearer $CANVAS_API_TOKEN" $CANVAS_URL/users/self

# Check internal networking
docker network ls
docker network inspect canvasscraper_canvas-network
```

**Resource issues:**
```bash
# Check resource usage
docker stats
df -h

# Clean up Docker resources
docker system prune -a
docker volume prune
```

### Performance Optimization

**For small instances (t3.micro/small):**
```yaml
environment:
  - CONCURRENT_DOWNLOADS=2
  - MAX_FILE_SIZE_MB=25
  - CHUNK_SIZE=500
deploy:
  resources:
    limits:
      memory: 1G
```

**For large instances (t3.large+):**
```yaml
environment:
  - CONCURRENT_DOWNLOADS=10
  - MAX_FILE_SIZE_MB=200
  - CHUNK_SIZE=2000
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
```

## 📚 Additional Resources

- **Docker Compose Documentation**: https://docs.docker.com/compose/
- **Canvas LMS API**: https://canvas.instructure.com/doc/api/
- **Supabase Documentation**: https://supabase.com/docs
- **Project Repository**: [Your repository URL]

For additional support, check the project issues or create a new issue with your docker-compose configuration and logs.