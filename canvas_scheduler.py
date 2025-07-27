#!/usr/bin/env python3
"""
Canvas Scraper with Built-in Scheduler
Runs the Canvas scraper every hour automatically
"""

import asyncio
import schedule
import time
from datetime import datetime
import logging
from canvas_client import CanvasClient
from canvas_supabase_demo import CanvasSupabaseIntegration

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CanvasScheduler:
    def __init__(self):
        self.integration = CanvasSupabaseIntegration()
        
    async def run_scraper(self):
        """Run the Canvas scraper and store results in Supabase."""
        try:
            logger.info("🚀 Starting scheduled Canvas scrape...")
            
            # Store courses in Supabase
            await self.integration.store_courses_in_supabase()
            
            # Get courses from database for content processing
            courses_response = self.integration.supabase.table('courses').select('id', 'name').execute()
            
            if courses_response.data:
                for course in courses_response.data:
                    course_id = course['id']
                    course_name = course['name']
                    
                    logger.info(f"📚 Processing course: {course_name}")
                    
                    # Store sample content (you can enhance this to process real content)
                    await self.integration.store_sample_content_extraction(course_id)
            
            # Create sync job record
            await self.integration.create_sample_sync_job()
            
            logger.info("✅ Scheduled scrape completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Scheduled scrape failed: {e}")
    
    def schedule_job(self):
        """Schedule the scraper to run every hour."""
        logger.info("⏰ Scheduling Canvas scraper to run every hour")
        
        # Schedule to run every hour
        schedule.every().hour.do(lambda: asyncio.run(self.run_scraper()))
        
        # Also run immediately on startup
        asyncio.run(self.run_scraper())
        
        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    logger.info("🎯 Canvas Scheduler Starting...")
    scheduler = CanvasScheduler()
    scheduler.schedule_job()