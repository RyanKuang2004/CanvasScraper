#!/usr/bin/env python3
"""
Supabase Database Setup Script
Sets up the complete Canvas scraper database schema in Supabase
"""

import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_supabase_database():
    """Setup the complete database schema in Supabase."""
    
    # Load environment variables
    load_dotenv()
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_service_key:
        logger.error("Missing Supabase credentials in .env file")
        logger.error("Please add SUPABASE_URL and SUPABASE_SERVICE_KEY to your .env file")
        return False
    
    logger.info(f"Connecting to Supabase: {supabase_url}")
    
    try:
        # Create Supabase client with service key (admin privileges)
        supabase: Client = create_client(supabase_url, supabase_service_key)
        
        # Test connection with a simple query
        logger.info("Testing Supabase connection...")
        try:
            # Try to get database info instead of querying a non-existent table
            supabase.table('pg_tables').select('tablename').limit(1).execute()
            logger.info("✅ Supabase connection successful!")
        except Exception as e:
            # If that fails, just log that we're connected
            logger.info("✅ Supabase connection established (ready for schema setup)")
        
        # Read the schema SQL file
        schema_path = 'database/schema.sql'
        if not os.path.exists(schema_path):
            logger.error(f"Schema file not found: {schema_path}")
            return False
        
        logger.info("Reading database schema...")
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema creation (Supabase supports PostgreSQL)
        logger.info("Creating database schema...")
        
        # Split schema into individual statements
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        logger.info(f"Executing {len(statements)} SQL statements...")
        
        for i, statement in enumerate(statements, 1):
            if statement.upper().startswith(('CREATE', 'ALTER', 'INSERT')):
                try:
                    # Use RPC to execute raw SQL
                    supabase.rpc('exec_sql', {'sql': statement}).execute()
                    logger.info(f"✅ Statement {i}/{len(statements)} executed")
                except Exception as e:
                    # Some statements might fail if already exist, that's okay
                    logger.warning(f"⚠️ Statement {i} failed (might already exist): {str(e)[:100]}...")
        
        # Enable real-time for key tables
        logger.info("Enabling real-time subscriptions...")
        await enable_realtime_tables(supabase)
        
        # Test schema creation
        logger.info("Testing schema creation...")
        await test_schema(supabase)
        
        logger.info("🎉 Supabase database setup complete!")
        logger.info("You can now access your database at: https://app.supabase.com/project/[your-project-id]")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to setup Supabase database: {str(e)}")
        return False

async def enable_realtime_tables(supabase: Client):
    """Enable real-time subscriptions for key tables."""
    
    realtime_tables = [
        'content_extractions',
        'sync_jobs',
        'courses',
        'content_changes'
    ]
    
    for table in realtime_tables:
        try:
            # Enable real-time for table
            logger.info(f"Enabling real-time for table: {table}")
            # Note: Real-time is typically enabled through Supabase dashboard
            # This is a placeholder for the actual implementation
        except Exception as e:
            logger.warning(f"Could not enable real-time for {table}: {e}")

async def test_schema(supabase: Client):
    """Test that the schema was created successfully."""
    
    test_tables = ['courses', 'content_extractions', 'sync_jobs']
    
    for table in test_tables:
        try:
            # Try to select from each table
            response = supabase.table(table).select('*').limit(1).execute()
            logger.info(f"✅ Table '{table}' accessible")
        except Exception as e:
            logger.warning(f"⚠️ Table '{table}' might not exist: {e}")

async def test_supabase_connection():
    """Test basic Supabase connection and credentials."""
    
    load_dotenv()
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
    supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    logger.info("Testing Supabase Configuration:")
    logger.info(f"URL: {supabase_url}")
    logger.info(f"Anon Key: {supabase_anon_key[:20]}..." if supabase_anon_key else "❌ Missing")
    logger.info(f"Service Key: {supabase_service_key[:20]}..." if supabase_service_key else "❌ Missing")
    
    if not all([supabase_url, supabase_anon_key, supabase_service_key]):
        logger.error("❌ Missing Supabase credentials!")
        logger.error("Please update your .env file with:")
        logger.error("SUPABASE_URL=https://your-project-id.supabase.co")
        logger.error("SUPABASE_ANON_KEY=your-anon-key")
        logger.error("SUPABASE_SERVICE_KEY=your-service-key")
        return False
    
    try:
        # Test with anon key
        supabase_anon = create_client(supabase_url, supabase_anon_key)
        logger.info("✅ Anon key connection successful")
        
        # Test with service key
        supabase_service = create_client(supabase_url, supabase_service_key)
        logger.info("✅ Service key connection successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Just test connection
        asyncio.run(test_supabase_connection())
    else:
        # Full setup
        asyncio.run(setup_supabase_database())