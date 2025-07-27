#!/usr/bin/env python3
"""
Canvas + Supabase Integration Demo
Demonstrates storing Canvas data in Supabase database
"""

import os
import asyncio
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from canvas_client import CanvasClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CanvasSupabaseIntegration:
    def __init__(self):
        load_dotenv()
        
        # Initialize Supabase client
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_KEY')  # Use service key for write operations
        )
        
        # Initialize Canvas client
        self.canvas = CanvasClient()
    
    async def store_courses_in_supabase(self):
        """Fetch Canvas courses and store them in Supabase."""
        
        logger.info("🎓 Fetching courses from Canvas...")
        
        # Get active courses from Canvas
        courses = await self.canvas.get_active_courses()
        
        if not courses:
            logger.warning("No active courses found")
            return
        
        logger.info(f"Found {len(courses)} active courses")
        
        # Store each course in Supabase
        for course in courses:
            try:
                course_data = {
                    'id': course['id'],
                    'name': course['name'],
                    'course_code': course.get('course_code'),
                    'enrollment_state': course.get('workflow_state', 'active'),
                    'last_synced_at': datetime.utcnow().isoformat()
                }
                
                # Use upsert to handle existing courses
                response = self.supabase.table('courses').upsert(
                    course_data,
                    on_conflict='id'
                ).execute()
                
                logger.info(f"✅ Stored course: {course['name']}")
                
            except Exception as e:
                logger.error(f"❌ Failed to store course {course['name']}: {e}")
        
        logger.info("🎉 All courses stored in Supabase!")
    
    async def store_sample_content_extraction(self, course_id: int):
        """Store a sample content extraction for demonstration."""
        
        logger.info(f"📄 Creating sample content extraction for course {course_id}...")
        
        sample_text = """
        This is a sample extracted text from a Canvas course document. 
        It demonstrates how text extraction would work with PDFs, PPTX, 
        and other file formats from Canvas courses.
        
        Key topics covered:
        - Canvas API integration
        - Text extraction from multiple formats
        - Database storage with Supabase
        - Real-time dashboard capabilities
        """
        
        content_hash = hashlib.sha256(sample_text.encode()).hexdigest()
        text_hash = hashlib.sha256(sample_text.encode()).hexdigest()
        
        extraction_data = {
            'source_type': 'file',
            'source_id': 'sample_123',
            'course_id': course_id,
            'original_title': 'Sample Canvas Document.pdf',
            'original_content_type': 'application/pdf',
            'original_file_size': 245760,  # ~240KB
            'extracted_text': sample_text,
            'text_preview': sample_text[:200] + '...',
            'extraction_method': 'pdfplumber',
            'extraction_status': 'success',
            'character_count': len(sample_text),
            'word_count': len(sample_text.split()),
            'content_hash': content_hash,
            'text_hash': text_hash,
            'extracted_at': datetime.utcnow().isoformat()
        }
        
        try:
            response = self.supabase.table('content_extractions').upsert(
                extraction_data,
                on_conflict='source_type,source_id,course_id'
            ).execute()
            
            logger.info("✅ Sample content extraction stored!")
            return response.data[0]['id']
            
        except Exception as e:
            logger.error(f"❌ Failed to store content extraction: {e}")
            return None
    
    async def create_sample_sync_job(self):
        """Create a sample sync job to demonstrate monitoring."""
        
        logger.info("🔄 Creating sample sync job...")
        
        sync_job_data = {
            'job_type': 'demo_sync',
            'status': 'completed',
            'total_items': 15,
            'processed_items': 15,
            'failed_items': 0,
            'started_at': datetime.utcnow().isoformat(),
            'completed_at': datetime.utcnow().isoformat(),
            'result_summary': {
                'courses_processed': 3,
                'files_extracted': 12,
                'pages_processed': 8,
                'total_text_extracted': '45,230 characters',
                'success_rate': '100%'
            }
        }
        
        try:
            response = self.supabase.table('sync_jobs').insert(sync_job_data).execute()
            logger.info("✅ Sample sync job created!")
            return response.data[0]['id']
            
        except Exception as e:
            logger.error(f"❌ Failed to create sync job: {e}")
            return None
    
    async def show_dashboard_data(self):
        """Display data from Supabase to show what's stored."""
        
        logger.info("📊 Retrieving data from Supabase...")
        
        try:
            # Get courses
            courses = self.supabase.table('courses').select('*').execute()
            logger.info(f"📚 Courses in database: {len(courses.data)}")
            for course in courses.data:
                logger.info(f"   - {course['name']} (ID: {course['id']})")
            
            # Get content extractions
            extractions = self.supabase.table('content_extractions').select('*').execute()
            logger.info(f"📄 Content extractions: {len(extractions.data)}")
            for extraction in extractions.data:
                logger.info(f"   - {extraction['original_title']} ({extraction['word_count']} words)")
            
            # Get sync jobs
            jobs = self.supabase.table('sync_jobs').select('*').execute()
            logger.info(f"🔄 Sync jobs: {len(jobs.data)}")
            for job in jobs.data:
                logger.info(f"   - {job['job_type']} ({job['status']})")
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve data: {e}")

async def main():
    """Main demonstration function."""
    
    print("🚀 Canvas + Supabase Integration Demo")
    print("=" * 50)
    
    integration = CanvasSupabaseIntegration()
    
    # Step 1: Store Canvas courses in Supabase
    await integration.store_courses_in_supabase()
    print()
    
    # Step 2: Get a course ID for demonstration
    courses_response = integration.supabase.table('courses').select('id', 'name').limit(1).execute()
    if courses_response.data:
        course_id = courses_response.data[0]['id']
        course_name = courses_response.data[0]['name']
        
        logger.info(f"📚 Using course '{course_name}' for demo (ID: {course_id})")
        
        # Step 3: Store sample content extraction
        await integration.store_sample_content_extraction(course_id)
        print()
    
    # Step 4: Create sample sync job
    await integration.create_sample_sync_job()
    print()
    
    # Step 5: Show what's in the database
    await integration.show_dashboard_data()
    print()
    
    # Step 6: Show dashboard access
    logger.info("🎉 Demo complete! Check your Supabase dashboard:")
    logger.info("   📊 Table Editor: https://app.supabase.com/project/ffkyenaokthdmcykymlj/editor")
    logger.info("   📈 You can now see your Canvas data in real-time!")

if __name__ == "__main__":
    asyncio.run(main())