#\!/bin/bash

echo "🔍 Canvas Scraper Troubleshooting Script"
echo "========================================"
echo

# Check if we're on the EC2 instance
if [[ \! -f /home/ec2-user/canvas_client.py ]]; then
    echo "❌ This script should be run on your EC2 instance"
    echo "SSH to your instance first:"
    echo "ssh -i ~/.ssh/canvas-scraper-keypair.pem ec2-user@YOUR_INSTANCE_IP"
    exit 1
fi

echo "1. Checking if run_scraper.sh exists and permissions..."
if [[ -f /home/ec2-user/run_scraper.sh ]]; then
    echo "✅ run_scraper.sh exists"
    ls -la /home/ec2-user/run_scraper.sh
    echo
    echo "📄 Contents of run_scraper.sh:"
    cat /home/ec2-user/run_scraper.sh
else
    echo "❌ run_scraper.sh does not exist"
    echo "Creating the script now..."
    
    cat > /home/ec2-user/run_scraper.sh << 'SCRIPT_EOF'
#\!/bin/bash
echo "$(date): Starting Canvas scraper..." >> /home/ec2-user/scraper.log
docker exec canvas-scraper python canvas_client.py >> /home/ec2-user/scraper.log 2>&1
echo "$(date): Canvas scraper finished with exit code: $?" >> /home/ec2-user/scraper.log
echo "----------------------------------------" >> /home/ec2-user/scraper.log
SCRIPT_EOF
    
    chmod +x /home/ec2-user/run_scraper.sh
    echo "✅ Created run_scraper.sh with execute permissions"
fi

echo
echo "2. Checking Docker containers..."
echo "Running containers:"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

echo
echo "All containers (including stopped):"
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

echo
echo "3. Testing Docker exec command..."
if docker ps | grep -q canvas-scraper; then
    echo "✅ canvas-scraper container is running"
    echo "Testing direct execution:"
    docker exec canvas-scraper python --version
    echo
    echo "Testing Canvas client import:"
    docker exec canvas-scraper python -c "import canvas_client; print('Canvas client imports successfully')" || echo "❌ Canvas client import failed"
else
    echo "❌ canvas-scraper container is not running"
    echo "Available containers:"
    docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
    
    echo
    echo "Attempting to start the container..."
    if docker ps -a | grep -q canvas-scraper; then
        docker start canvas-scraper
        echo "Container start attempted. Checking status:"
        docker ps | grep canvas-scraper || echo "Failed to start container"
    else
        echo "❌ No canvas-scraper container found at all"
        echo "You may need to rebuild the container:"
        echo "sudo docker build -t canvas-scraper:latest ."
        echo "sudo docker run -d --name canvas-scraper --restart unless-stopped --env-file .env -v /home/ec2-user/logs:/app/logs canvas-scraper:latest tail -f /dev/null"
    fi
fi

echo
echo "4. Checking environment file..."
if [[ -f /home/ec2-user/.env ]]; then
    echo "✅ .env file exists"
    echo "Environment variables (masked):"
    sed 's/=.*/=***MASKED***/' /home/ec2-user/.env
else
    echo "❌ .env file missing"
fi

echo
echo "5. Checking Canvas client file..."
if [[ -f /home/ec2-user/canvas_client.py ]]; then
    echo "✅ canvas_client.py exists"
    head -5 /home/ec2-user/canvas_client.py
else
    echo "❌ canvas_client.py missing"
fi

echo
echo "6. Testing manual scraper execution..."
if docker ps | grep -q canvas-scraper; then
    echo "Attempting manual execution with output:"
    timeout 30 docker exec canvas-scraper python canvas_client.py || echo "Execution timed out or failed"
else
    echo "❌ Cannot test - container not running"
fi

echo
echo "7. Checking cron service..."
sudo systemctl status crond --no-pager || echo "Cron service check failed"

echo
echo "8. Checking current cron jobs..."
crontab -l || echo "No cron jobs found"

echo
echo "🎯 Troubleshooting complete\!"
echo "Run this script on your EC2 instance to diagnose the issue."
