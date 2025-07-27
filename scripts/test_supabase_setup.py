#!/usr/bin/env python3
"""
Test Supabase setup and basic functionality
"""

import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_supabase_setup():
    """Test that Supabase is properly configured and tables exist."""
    
    load_dotenv()
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_anon_key:
        logger.error("❌ Missing Supabase credentials")
        return False
    
    try:
        # Create client
        supabase: Client = create_client(supabase_url, supabase_anon_key)
        logger.info("✅ Supabase client created successfully")
        
        # Test tables exist
        tables_to_test = ['courses', 'content_extractions', 'sync_jobs']
        
        for table in tables_to_test:
            try:
                response = supabase.table(table).select('*').limit(1).execute()
                logger.info(f"✅ Table '{table}' accessible")
            except Exception as e:
                logger.error(f"❌ Table '{table}' not accessible: {e}")
                return False
        
        # Test inserting a sample course
        logger.info("Testing data insertion...")
        
        test_course = {
            'id': 999999,
            'name': 'Test Course - Canvas Scraper',
            'course_code': 'TEST101',
            'enrollment_state': 'active'
        }
        
        try:
            # Insert test course
            response = supabase.table('courses').insert(test_course).execute()
            logger.info("✅ Test course inserted successfully")
            
            # Verify insertion
            response = supabase.table('courses').select('*').eq('id', 999999).execute()
            if response.data:
                logger.info(f"✅ Test course retrieved: {response.data[0]['name']}")
            
            # Clean up test data
            supabase.table('courses').delete().eq('id', 999999).execute()
            logger.info("✅ Test course cleaned up")
            
        except Exception as e:
            logger.error(f"❌ Data insertion test failed: {e}")
            return False
        
        # Test content extraction table
        logger.info("Testing content extraction table...")
        
        test_extraction = {
            'source_type': 'test',
            'source_id': 'test_123',
            'course_id': None,  # Allow null for test
            'original_title': 'Test Content',
            'extracted_text': 'This is test extracted text content.',
            'extraction_status': 'success',
            'character_count': 37,
            'word_count': 6
        }
        
        try:
            # Insert test extraction
            response = supabase.table('content_extractions').insert(test_extraction).execute()
            extraction_id = response.data[0]['id']
            logger.info("✅ Test extraction inserted successfully")
            
            # Clean up
            supabase.table('content_extractions').delete().eq('id', extraction_id).execute()
            logger.info("✅ Test extraction cleaned up")
            
        except Exception as e:
            logger.error(f"❌ Content extraction test failed: {e}")
            return False
        
        logger.info("🎉 Supabase setup is working perfectly!")
        logger.info("🚀 Ready to integrate with Canvas scraper!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Supabase setup test failed: {e}")
        return False

async def show_dashboard_info():
    """Show information about accessing the Supabase dashboard."""
    
    load_dotenv()
    supabase_url = os.getenv('SUPABASE_URL')
    
    if supabase_url:
        project_id = supabase_url.split('//')[1].split('.')[0]
        dashboard_url = f"https://app.supabase.com/project/{project_id}"
        
        logger.info("📊 Supabase Dashboard Access:")
        logger.info(f"   Dashboard: {dashboard_url}")
        logger.info(f"   Table Editor: {dashboard_url}/editor")
        logger.info(f"   SQL Editor: {dashboard_url}/sql")
        logger.info("📝 You can view and query your data directly in the dashboard!")

if __name__ == "__main__":
    print("🔍 Testing Supabase Setup for Canvas Scraper")
    print("=" * 50)
    
    success = asyncio.run(test_supabase_setup())
    
    if success:
        asyncio.run(show_dashboard_info())
    else:
        print("\n❌ Setup incomplete. Please run the SQL setup first:")
        print("1. Go to your Supabase dashboard")
        print("2. Open the SQL Editor")
        print("3. Copy and paste the contents of 'supabase_quick_setup.sql'")
        print("4. Run the SQL to create tables")
        print("5. Run this test script again")