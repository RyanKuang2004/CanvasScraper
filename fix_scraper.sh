#!/bin/bash

echo "🔧 Quick Fix for Canvas Scraper"
echo "================================"

# This script should be run on your EC2 instance
# Usage: ./fix_scraper.sh

echo "1. Stopping existing container..."
docker stop canvas-scraper || echo "Container already stopped"
docker rm canvas-scraper || echo "Container already removed"

echo "2. Rebuilding container with correct setup..."
sudo docker build -t canvas-scraper:latest .

echo "3. Creating/updating environment file with correct region..."
cat > .env << EOF
CANVAS_API_TOKEN=$(aws ssm get-parameter --name "/canvas-scraper/canvas-api-token" --with-decryption --region ap-southeast-2 --query 'Parameter.Value' --output text)
SUPABASE_URL=$(aws ssm get-parameter --name "/canvas-scraper/supabase-url" --region ap-southeast-2 --query 'Parameter.Value' --output text 2>/dev/null || echo "")
SUPABASE_ANON_KEY=$(aws ssm get-parameter --name "/canvas-scraper/supabase-anon-key" --with-decryption --region ap-southeast-2 --query 'Parameter.Value' --output text 2>/dev/null || echo "")
SUPABASE_SERVICE_KEY=$(aws ssm get-parameter --name "/canvas-scraper/supabase-service-key" --with-decryption --region ap-southeast-2 --query 'Parameter.Value' --output text 2>/dev/null || echo "")
EOF

echo "4. Starting container with proper configuration..."
sudo docker run -d \
    --name canvas-scraper \
    --restart unless-stopped \
    --env-file .env \
    -v /home/ec2-user/logs:/app/logs \
    canvas-scraper:latest tail -f /dev/null

echo "5. Creating run_scraper.sh script..."
cat > /home/ec2-user/run_scraper.sh << 'EOF'
#!/bin/bash
echo "$(date): Starting Canvas scraper..." >> /home/ec2-user/scraper.log
docker exec canvas-scraper python canvas_client.py >> /home/ec2-user/scraper.log 2>&1
exit_code=$?
echo "$(date): Canvas scraper finished with exit code: $exit_code" >> /home/ec2-user/scraper.log
echo "----------------------------------------" >> /home/ec2-user/scraper.log
EOF

chmod +x /home/ec2-user/run_scraper.sh

echo "6. Testing the setup..."
echo "Container status:"
docker ps | grep canvas-scraper

echo "Testing Canvas scraper..."
docker exec canvas-scraper python canvas_client.py

echo "7. Setting up cron job..."
# Remove any existing cron job for canvas scraper
(crontab -l 2>/dev/null | grep -v "canvas-scraper\|docker exec canvas-scraper") | crontab -

# Add new cron job
(crontab -l 2>/dev/null; echo "0 * * * * /home/ec2-user/run_scraper.sh") | crontab -

echo "8. Starting cron service..."
sudo systemctl enable crond
sudo systemctl start crond
sudo systemctl status crond --no-pager

echo "✅ Setup complete!"
echo ""
echo "To test manually: /home/ec2-user/run_scraper.sh"
echo "To check logs: tail -f /home/ec2-user/scraper.log"
echo "To check cron: crontab -l"