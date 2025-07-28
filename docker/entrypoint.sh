#!/bin/bash
# Enhanced Canvas Scraper Entrypoint Script
# Handles initialization, health checks, and graceful shutdown

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Function to check environment variables
check_env() {
    log "Checking environment variables..."
    
    # Required variables
    if [[ -z "${CANVAS_API_TOKEN}" ]]; then
        error "CANVAS_API_TOKEN is required"
        exit 1
    fi
    
    if [[ -z "${CANVAS_URL}" ]]; then
        error "CANVAS_URL is required"
        exit 1
    fi
    
    # Optional but recommended
    if [[ -z "${SUPABASE_URL}" ]] || [[ -z "${SUPABASE_ANON_KEY}" ]]; then
        warn "Supabase credentials not set - data will not be stored persistently"
        warn "Set SUPABASE_URL and SUPABASE_ANON_KEY for full functionality"
    fi
    
    log "Environment check completed"
}

# Function to test Canvas API connectivity
test_canvas_api() {
    log "Testing Canvas API connectivity..."
    
    local response=$(curl -s -w "%{http_code}" \
        -H "Authorization: Bearer ${CANVAS_API_TOKEN}" \
        "${CANVAS_URL}/users/self" \
        -o /dev/null)
    
    if [[ "$response" == "200" ]]; then
        log "Canvas API connection successful"
    else
        error "Canvas API connection failed (HTTP $response)"
        error "Check your CANVAS_API_TOKEN and CANVAS_URL"
        exit 1
    fi
}

# Function to test Supabase connectivity
test_supabase() {
    if [[ -n "${SUPABASE_URL}" ]] && [[ -n "${SUPABASE_ANON_KEY}" ]]; then
        log "Testing Supabase connectivity..."
        
        local response=$(curl -s -w "%{http_code}" \
            -H "apikey: ${SUPABASE_ANON_KEY}" \
            -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
            "${SUPABASE_URL}/rest/v1/" \
            -o /dev/null)
        
        if [[ "$response" == "200" ]]; then
            log "Supabase connection successful"
        else
            warn "Supabase connection failed (HTTP $response) - continuing without persistence"
        fi
    fi
}

# Function to setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p /app/logs
    mkdir -p /app/data
    mkdir -p /app/downloads
    mkdir -p /app/config
    
    # Ensure config file exists
    if [[ ! -f /app/config/courses.yml ]]; then
        log "Creating default courses.yml configuration..."
        cat > /app/config/courses.yml << 'EOF'
# Canvas Course Configuration
# Configure which courses to scrape and processing preferences

# List of Canvas course IDs to process
enabled_courses: []
  # Add your course IDs here, e.g.:
  # - "12345"
  # - "67890"

# Scraping preferences
scraping_preferences:
  # File types to process
  file_types:
    - pdf
    - pptx
    - docx
  
  # Maximum file size in MB
  max_file_size_mb: 50
  
  # Skip hidden modules
  skip_hidden_modules: true
  
  # Concurrent processing
  concurrent_downloads: 3

# Text processing settings
text_processing:
  chunk_size: 1000
  chunk_overlap: 200
  preserve_structure: true

# Scheduling configuration
scheduling:
  enabled: true
  timezone: "Australia/Melbourne"
  times:
    - "12:00"  # 12 PM
    - "20:00"  # 8 PM

# Deduplication settings
deduplication:
  enabled: true
  check_content_changes: true
  fingerprint_algorithm: "sha256"
EOF
        warn "Default configuration created - please edit /app/config/courses.yml"
        warn "Add your Canvas course IDs to enabled_courses list"
    fi
    
    log "Directory setup completed"
}

# Function to initialize application
initialize_app() {
    log "Initializing Canvas Scraper Enhanced..."
    
    # Set Python path
    export PYTHONPATH="/app:${PYTHONPATH}"
    
    # Create log file
    touch /app/logs/canvas_scraper.log
    
    # Test Python imports
    log "Testing Python dependencies..."
    python -c "
import sys
sys.path.insert(0, '/app')
try:
    from src.canvas_orchestrator import CanvasOrchestrator
    from src.supabase_client import get_supabase_client
    print('✅ All dependencies imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"
    
    if [[ $? -ne 0 ]]; then
        error "Python dependency check failed"
        exit 1
    fi
    
    log "Application initialization completed"
}

# Set up cron job if requested
setup_cron() {
    if [[ "$ENABLE_CRON" == "true" ]]; then
        log "Setting up cron job for scheduled execution..."
        
        # Create cron entry
        CRON_SCHEDULE="${CRON_SCHEDULE:-0 2 * * *}"  # Default: 2 AM daily
        echo "$CRON_SCHEDULE cd /app && python scripts/run_scraper.py >> logs/cron.log 2>&1" > /tmp/crontab
        
        # Install cron job (requires running as root or with appropriate permissions)
        if command -v crontab >/dev/null 2>&1; then
            crontab /tmp/crontab
            log "Cron job installed: $CRON_SCHEDULE"
            
            # Start cron daemon
            if command -v cron >/dev/null 2>&1; then
                cron
                log "Cron daemon started"
            fi
        else
            warn "Cron not available, skipping cron setup"
        fi
    fi
}

# Health check endpoint (simple HTTP server)
start_health_server() {
    if [[ "$ENABLE_HEALTH_SERVER" == "true" ]]; then
        log "Starting health check server on port 8080..."
        python -c "
import http.server
import socketserver
import threading
import time

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"status\": \"healthy\", \"service\": \"canvas-scraper\"}')
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    with socketserver.TCPServer(('', 8080), HealthHandler) as httpd:
        httpd.serve_forever()

# Start server in background thread
threading.Thread(target=start_server, daemon=True).start()
" &
    fi
}

# Function to handle graceful shutdown
cleanup() {
    log "Shutting down Canvas Scraper..."
    
    # Kill any running Python processes
    pkill -f "python.*canvas" || true
    
    # Wait a moment for cleanup
    sleep 2
    
    log "Shutdown completed"
    exit 0
}

# Function to show startup banner
show_banner() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "       Canvas Scraper Enhanced v2.0"
    echo "=================================================="
    echo "Features:"
    echo "• Multi-format file processing (PDF, PPTX, DOCX)"
    echo "• Intelligent text chunking with deduplication"
    echo "• Supabase integration with full-text search"
    echo "• Melbourne timezone scheduling"
    echo "• Docker deployment ready"
    echo "=================================================="
    echo -e "${NC}"
}

# Function to validate configuration
validate_config() {
    log "Validating configuration..."
    
    if [[ -f /app/config/courses.yml ]]; then
        # Basic YAML syntax check
        python -c "
import yaml
try:
    with open('/app/config/courses.yml', 'r') as f:
        config = yaml.safe_load(f)
    if not config.get('enabled_courses'):
        print('⚠️  No courses configured in enabled_courses')
    else:
        print(f'✅ Configuration valid - {len(config[\"enabled_courses\"])} courses enabled')
except Exception as e:
    print(f'❌ Configuration error: {e}')
    exit(1)
"
        if [[ $? -ne 0 ]]; then
            error "Configuration validation failed"
            exit 1
        fi
    else
        error "Configuration file not found: /app/config/courses.yml"
        exit 1
    fi
}

# Function to run health check
health_check() {
    log "Running health check..."
    python /healthcheck.py
    if [[ $? -eq 0 ]]; then
        log "Health check passed"
    else
        warn "Health check failed - continuing anyway"
    fi
}

# Main execution
main() {
    # Show banner
    show_banner
    
    # Setup signal handlers for graceful shutdown
    trap cleanup SIGTERM SIGINT
    
    # Run initialization steps
    check_env
    setup_directories
    test_canvas_api
    test_supabase
    initialize_app
    validate_config
    health_check
    
    log "Starting Canvas Scraper Enhanced..."
    log "Command: $@"
    
    # Execute the provided command or default
    if [[ $# -eq 0 ]]; then
        log "No command provided, starting enhanced orchestrator..."
        exec python scripts/run_enhanced_scraper.py run
    else
        log "Executing command: $*"
        exec "$@"
    fi
}

# Run main function with all arguments
main "$@"