#!/bin/bash

# Canvas Scraper Docker Deployment Script
# Production-ready deployment with health checks and rollback capability

set -e

# Configuration
PROJECT_NAME="canvas-scraper"
IMAGE_NAME="canvas-scraper"
CONTAINER_NAME="canvas-scraper-prod"
HEALTH_CHECK_URL="http://localhost:8080/health"
DEPLOYMENT_TIMEOUT=300  # 5 minutes

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking deployment prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check .env file
    if [[ ! -f .env ]]; then
        error ".env file not found. Copy from .env.example and configure."
        exit 1
    fi
    
    # Check required environment variables
    source .env
    if [[ -z "$CANVAS_API_TOKEN" ]]; then
        error "CANVAS_API_TOKEN not set in .env file"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

# Build new image
build_image() {
    local version=${1:-latest}
    log "Building Docker image: ${IMAGE_NAME}:${version}"
    
    docker build \
        --target production \
        --tag ${IMAGE_NAME}:${version} \
        --tag ${IMAGE_NAME}:latest \
        .
    
    log "Docker image built successfully"
}

# Health check function
wait_for_health() {
    local container_name=$1
    local timeout=${2:-60}
    local interval=5
    local elapsed=0
    
    log "Waiting for container to become healthy..."
    
    while [[ $elapsed -lt $timeout ]]; do
        if docker exec $container_name python /healthcheck.py &>/dev/null; then
            log "Container is healthy!"
            return 0
        fi
        
        info "Health check failed, retrying in ${interval}s... (${elapsed}/${timeout}s)"
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    error "Container failed to become healthy within ${timeout}s"
    return 1
}

# Blue-green deployment
deploy_blue_green() {
    local version=${1:-latest}
    local current_container="${CONTAINER_NAME}"
    local new_container="${CONTAINER_NAME}-new"
    
    log "Starting blue-green deployment..."
    
    # Stop and remove any existing new container
    if docker ps -a --format '{{.Names}}' | grep -q "^${new_container}$"; then
        log "Removing existing ${new_container} container"
        docker stop $new_container || true
        docker rm $new_container || true
    fi
    
    # Start new container
    log "Starting new container: ${new_container}"
    docker run -d \
        --name $new_container \
        --env-file .env \
        -v canvas_logs:/app/logs \
        -v canvas_data:/app/data \
        -p 8081:8080 \
        --restart unless-stopped \
        ${IMAGE_NAME}:${version}
    
    # Wait for new container to be healthy
    if ! wait_for_health $new_container 120; then
        error "New container failed health check, rolling back..."
        docker stop $new_container || true
        docker rm $new_container || true
        exit 1
    fi
    
    # If current container exists, stop it
    if docker ps --format '{{.Names}}' | grep -q "^${current_container}$"; then
        log "Stopping current container: ${current_container}"
        docker stop $current_container
        
        # Backup current container (rename)
        backup_name="${current_container}-backup-$(date +%Y%m%d-%H%M%S)"
        docker rename $current_container $backup_name
        log "Current container backed up as: ${backup_name}"
    fi
    
    # Promote new container to current
    log "Promoting new container to production..."
    docker stop $new_container
    docker rename $new_container $current_container
    
    # Start with production port mapping
    docker run -d \
        --name ${current_container}-live \
        --env-file .env \
        -v canvas_logs:/app/logs \
        -v canvas_data:/app/data \
        -p 8080:8080 \
        --restart unless-stopped \
        ${IMAGE_NAME}:${version}
    
    # Remove the temporary renamed container
    docker rm $current_container
    docker rename ${current_container}-live $current_container
    
    # Final health check
    if ! wait_for_health $current_container 60; then
        error "Production container failed final health check!"
        exit 1
    fi
    
    log "Blue-green deployment completed successfully!"
}

# Rolling deployment (simpler, faster)
deploy_rolling() {
    local version=${1:-latest}
    
    log "Starting rolling deployment..."
    
    # Stop existing container if running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "Stopping existing container"
        docker stop $CONTAINER_NAME
        docker rm $CONTAINER_NAME
    fi
    
    # Start new container
    log "Starting new container with updated image"
    docker run -d \
        --name $CONTAINER_NAME \
        --env-file .env \
        -v canvas_logs:/app/logs \
        -v canvas_data:/app/data \
        -p 8080:8080 \
        --restart unless-stopped \
        ${IMAGE_NAME}:${version}
    
    # Health check
    if ! wait_for_health $CONTAINER_NAME 120; then
        error "Deployment failed health check!"
        exit 1
    fi
    
    log "Rolling deployment completed successfully!"
}

# Rollback function
rollback() {
    log "Starting rollback procedure..."
    
    # Find most recent backup
    backup_container=$(docker ps -a --format '{{.Names}}' | grep "^${CONTAINER_NAME}-backup-" | sort -r | head -1)
    
    if [[ -z "$backup_container" ]]; then
        error "No backup container found for rollback"
        exit 1
    fi
    
    log "Rolling back to: $backup_container"
    
    # Stop current container
    docker stop $CONTAINER_NAME || true
    docker rm $CONTAINER_NAME || true
    
    # Start backup container
    docker start $backup_container
    docker rename $backup_container $CONTAINER_NAME
    
    # Update port mapping
    docker stop $CONTAINER_NAME
    # Get the image from the backup container
    backup_image=$(docker inspect --format='{{.Config.Image}}' $CONTAINER_NAME)
    docker rm $CONTAINER_NAME
    
    docker run -d \
        --name $CONTAINER_NAME \
        --env-file .env \
        -v canvas_logs:/app/logs \
        -v canvas_data:/app/data \
        -p 8080:8080 \
        --restart unless-stopped \
        $backup_image
    
    log "Rollback completed successfully!"
}

# Cleanup old backups
cleanup_backups() {
    local keep_count=${1:-3}
    
    log "Cleaning up old backup containers (keeping last $keep_count)..."
    
    backup_containers=$(docker ps -a --format '{{.Names}}' | grep "^${CONTAINER_NAME}-backup-" | sort -r | tail -n +$((keep_count + 1)))
    
    if [[ -n "$backup_containers" ]]; then
        echo "$backup_containers" | xargs -r docker rm -f
        log "Cleanup completed"
    else
        log "No backups to clean up"
    fi
}

# Main deployment function
main() {
    local action=${1:-deploy}
    local version=${2:-latest}
    local deployment_type=${DEPLOYMENT_TYPE:-rolling}  # rolling or blue-green
    
    case $action in
        "build")
            check_prerequisites
            build_image $version
            ;;
        "deploy")
            check_prerequisites
            build_image $version
            
            case $deployment_type in
                "blue-green")
                    deploy_blue_green $version
                    ;;
                "rolling"|*)
                    deploy_rolling $version
                    ;;
            esac
            
            cleanup_backups 3
            log "Deployment completed! Container status:"
            docker ps --filter name=$CONTAINER_NAME
            ;;
        "rollback")
            rollback
            ;;
        "status")
            info "Container status:"
            docker ps --filter name=$CONTAINER_NAME
            echo
            info "Health check:"
            docker exec $CONTAINER_NAME python /healthcheck.py || true
            ;;
        "logs")
            docker logs --tail 100 -f $CONTAINER_NAME
            ;;
        "cleanup")
            cleanup_backups ${2:-3}
            ;;
        *)
            echo "Usage: $0 {build|deploy|rollback|status|logs|cleanup} [version]"
            echo
            echo "Commands:"
            echo "  build [version]     - Build Docker image"
            echo "  deploy [version]    - Deploy application (build + run)"
            echo "  rollback           - Rollback to previous version"
            echo "  status             - Show container status and health"
            echo "  logs               - Show container logs"
            echo "  cleanup [count]    - Clean up old backup containers"
            echo
            echo "Environment variables:"
            echo "  DEPLOYMENT_TYPE    - rolling (default) or blue-green"
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"