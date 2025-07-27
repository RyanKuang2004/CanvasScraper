# Canvas Scraper + Supabase Implementation Plan

## 🎯 Executive Summary

Integrating Supabase transforms your Canvas scraper into a modern web application with instant UI capabilities, managed database services, and real-time features - all while maintaining the sophisticated text extraction and sync capabilities.

**Timeline**: 4-5 weeks (2-3 weeks faster than PostgreSQL)
**Complexity**: Medium (simplified by Supabase managed services)
**Cost**: FREE (Supabase free tier covers all requirements)

## 🏗️ Implementation Phases

### Phase 1: Supabase Setup & Database Migration (Week 1)

#### 1.1 Supabase Project Creation
```bash
# 1. Create Supabase account and project
# 2. Get project URL and anon key
# 3. Configure environment variables

# New dependencies
pip install supabase>=1.0.0
pip install python-dotenv>=0.19.0
```

#### 1.2 Database Schema Setup
```python
# scripts/setup_supabase_schema.py
from supabase import create_client
import os

def setup_database():
    """Setup the complete database schema in Supabase."""
    
    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')  # Service key for admin operations
    )
    
    # Execute the same schema.sql file!
    with open('database/schema.sql', 'r') as f:
        schema_sql = f.read()
    
    # Supabase supports the exact same PostgreSQL schema
    supabase.rpc('exec_sql', {'sql': schema_sql})
    
    # Enable real-time for key tables
    enable_realtime_tables(supabase)
    
    # Setup Row-Level Security
    setup_security_policies(supabase)

def enable_realtime_tables(supabase):
    """Enable real-time subscriptions for key tables."""
    realtime_tables = [
        'content_extractions',
        'sync_jobs',
        'courses',
        'content_changes'
    ]
    
    for table in realtime_tables:
        supabase.rpc('enable_realtime', {'table_name': table})
```

#### 1.3 Environment Configuration
```bash
# .env file
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Keep existing Canvas configuration
CANVAS_API_TOKEN=your-canvas-token
CANVAS_URL=https://canvas.lms.unimelb.edu.au/api/v1
```

**Deliverables:**
- ✅ Supabase project with complete schema
- ✅ Real-time enabled tables
- ✅ Row-level security policies
- ✅ Environment configuration
- ✅ Connection testing and validation

### Phase 2: Enhanced Canvas Client with Supabase (Week 2)

#### 2.1 Supabase Canvas Client
```python
# src/canvas/supabase_client.py
from supabase import create_client, Client
from canvas_client import CanvasClient
import asyncio
import hashlib
from typing import Optional, List, Dict, Any

class SupabaseCanvasClient(CanvasClient):
    def __init__(self):
        super().__init__()
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_KEY')
        )
    
    async def sync_course_with_database(self, course_id: int) -> dict:
        """Enhanced sync that stores everything in Supabase."""
        
        # 1. Sync course metadata
        course_data = await self.get_course_info(course_id)
        await self._upsert_course(course_data)
        
        # 2. Sync modules and items
        modules = await self.get_modules(self._session, course_id)
        for module in modules:
            await self._upsert_module(module, course_id)
            
            items = await self.get_module_items(self._session, course_id, module['id'])
            for item in items:
                await self._upsert_module_item(item, course_id)
                
                # 3. Process content for text extraction
                if item['type'] in ['File', 'Page']:
                    await self._process_content_item(item, course_id)
        
        # 4. Update sync state
        await self._update_sync_state(course_id)
        
        return {"status": "success", "course_id": course_id}
    
    async def _process_content_item(self, item: dict, course_id: int):
        """Process and extract text from content items."""
        
        # Check if already processed
        existing = self.supabase.table('content_extractions') \
            .select('id, content_hash') \
            .eq('source_type', item['type'].lower()) \
            .eq('source_id', str(item['content_id'])) \
            .eq('course_id', course_id) \
            .execute()
        
        if item['type'] == 'File':
            await self._process_file_item(item, course_id, existing.data)
        elif item['type'] == 'Page':
            await self._process_page_item(item, course_id, existing.data)
    
    async def _process_file_item(self, item: dict, course_id: int, existing: list):
        """Download and extract text from file."""
        
        # Get file info
        file_info = await self.get_file_info(item['content_id'])
        if not file_info or file_info['content_type'] not in SUPPORTED_TYPES:
            return
        
        # Calculate content hash for deduplication
        file_content = await self.download_file_content(file_info['download_url'])
        content_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check if content changed
        if existing and existing[0]['content_hash'] == content_hash:
            return  # No changes, skip
        
        # Extract text
        extracted_text = await self.extract_text_from_content(
            file_content, 
            file_info['content_type']
        )
        
        # Store in Supabase
        extraction_data = {
            'source_type': 'file',
            'source_id': str(item['content_id']),
            'course_id': course_id,
            'original_title': file_info['display_name'],
            'original_content_type': file_info['content_type'],
            'original_file_size': len(file_content),
            'extracted_text': extracted_text,
            'text_preview': extracted_text[:500] if extracted_text else None,
            'extraction_method': self._get_extraction_method(file_info['content_type']),
            'character_count': len(extracted_text) if extracted_text else 0,
            'word_count': len(extracted_text.split()) if extracted_text else 0,
            'content_hash': content_hash,
            'text_hash': hashlib.sha256(extracted_text.encode()).hexdigest() if extracted_text else None,
            'extraction_status': 'success' if extracted_text else 'failed'
        }
        
        # Upsert (insert or update)
        result = self.supabase.table('content_extractions').upsert(
            extraction_data,
            on_conflict='source_type,source_id,course_id'
        ).execute()
        
        # Real-time update will automatically notify any connected UIs!
        return result
```

#### 2.2 Text Extraction Integration
```python
# src/extractors/supabase_extractor.py
class SupabaseTextExtractor:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.extractors = {
            'application/pdf': PDFExtractor(),
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': PPTXExtractor(),
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DOCXExtractor(),
            'text/html': HTMLExtractor()
        }
    
    async def extract_and_store(self, content: bytes, content_type: str, metadata: dict):
        """Extract text and store in Supabase with real-time updates."""
        
        extractor = self.extractors.get(content_type)
        if not extractor:
            return None
        
        try:
            # Extract text
            extracted_text = await extractor.extract_text(content)
            
            # Store in Supabase
            result = await self._store_extraction(extracted_text, metadata)
            
            # Automatic real-time notification to dashboard!
            return result
            
        except Exception as e:
            # Store error information
            await self._store_extraction_error(e, metadata)
            raise
```

**Deliverables:**
- ✅ Enhanced Canvas client with Supabase integration
- ✅ Text extraction pipeline with database storage
- ✅ Real-time content updates
- ✅ Deduplication and change detection
- ✅ Error handling and logging

### Phase 3: Instant Dashboard Access (Week 2)

#### 3.1 Supabase Built-in Dashboard
**Immediate access to:**
- **Table Browser**: View all courses, modules, extracted content
- **SQL Editor**: Run custom queries and analytics
- **Real-time Monitor**: Watch sync progress live
- **Data Export**: Download content in various formats

#### 3.2 Quick Custom Queries
```sql
-- View recent content extractions
SELECT 
    ce.original_title,
    ce.text_preview,
    ce.word_count,
    c.name as course_name,
    ce.extracted_at
FROM content_extractions ce
JOIN courses c ON ce.course_id = c.id
ORDER BY ce.extracted_at DESC
LIMIT 20;

-- Search across all content
SELECT 
    original_title,
    course_id,
    ts_headline(extracted_text, query) as highlighted_text
FROM content_extractions, 
     plainto_tsquery('quantum mechanics') query
WHERE to_tsvector('english', extracted_text) @@ query
ORDER BY ts_rank(to_tsvector('english', extracted_text), query) DESC;

-- Course content statistics
SELECT 
    c.name,
    COUNT(ce.id) as total_extractions,
    SUM(ce.word_count) as total_words,
    AVG(ce.word_count) as avg_words_per_file
FROM courses c
LEFT JOIN content_extractions ce ON c.id = ce.course_id
GROUP BY c.id, c.name
ORDER BY total_words DESC;
```

**Deliverables:**
- ✅ Immediate data access via Supabase dashboard
- ✅ Custom SQL queries for analysis
- ✅ Real-time data monitoring
- ✅ Export capabilities for external analysis

### Phase 4: Automated Sync with Real-time Updates (Week 3)

#### 4.1 Scheduler with Supabase Integration
```python
# src/scheduler/supabase_scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import asyncio

class SupabaseScheduler:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.scheduler = AsyncIOScheduler(
            jobstores={
                'default': SQLAlchemyJobStore(
                    url=f"postgresql://{supabase_client.db_credentials}"
                )
            }
        )
    
    async def setup_hourly_syncs(self):
        """Setup hourly sync jobs with real-time progress updates."""
        
        # Get all active courses
        courses = self.supabase.table('courses') \
            .select('id, name') \
            .eq('enrollment_state', 'active') \
            .execute()
        
        for course in courses.data:
            # Stagger sync times to distribute load
            minute_offset = hash(course['id']) % 60
            
            self.scheduler.add_job(
                func=self._sync_course_with_progress,
                trigger='cron',
                minute=minute_offset,
                args=[course['id']],
                id=f'hourly_sync_{course["id"]}',
                name=f'Sync {course["name"]}',
                replace_existing=True
            )
    
    async def _sync_course_with_progress(self, course_id: int):
        """Sync course with real-time progress updates."""
        
        # Create sync job record
        sync_job = self.supabase.table('sync_jobs').insert({
            'job_type': 'incremental_sync',
            'course_id': course_id,
            'status': 'running',
            'started_at': datetime.utcnow().isoformat()
        }).execute()
        
        job_id = sync_job.data[0]['id']
        
        try:
            # Perform sync with progress updates
            result = await self.canvas_client.sync_course_with_database(course_id)
            
            # Update job status - triggers real-time update to dashboard!
            self.supabase.table('sync_jobs').update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'result_summary': result
            }).eq('id', job_id).execute()
            
        except Exception as e:
            # Update job with error status
            self.supabase.table('sync_jobs').update({
                'status': 'failed',
                'completed_at': datetime.utcnow().isoformat(),
                'error_log': str(e)
            }).eq('id', job_id).execute()
            raise
```

#### 4.2 Real-time Sync Monitoring
```typescript
// Dashboard component for real-time sync monitoring
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export function SyncMonitor() {
    const [activeSyncs, setActiveSyncs] = useState([])
    const [recentJobs, setRecentJobs] = useState([])
    
    useEffect(() => {
        // Load initial data
        loadSyncJobs()
        
        // Setup real-time subscription
        const subscription = supabase
            .from('sync_jobs')
            .on('*', payload => {
                handleSyncUpdate(payload)
            })
            .subscribe()
        
        return () => subscription.unsubscribe()
    }, [])
    
    const handleSyncUpdate = (payload) => {
        const { eventType, new: newRecord, old: oldRecord } = payload
        
        if (eventType === 'INSERT') {
            if (newRecord.status === 'running') {
                setActiveSyncs(prev => [...prev, newRecord])
            }
        } else if (eventType === 'UPDATE') {
            if (newRecord.status === 'completed' || newRecord.status === 'failed') {
                setActiveSyncs(prev => prev.filter(job => job.id !== newRecord.id))
                setRecentJobs(prev => [newRecord, ...prev.slice(0, 9)])
            }
        }
    }
    
    return (
        <div className="sync-monitor">
            <h3>Active Syncs ({activeSyncs.length})</h3>
            {activeSyncs.map(job => (
                <SyncJobCard key={job.id} job={job} isActive={true} />
            ))}
            
            <h3>Recent Jobs</h3>
            {recentJobs.map(job => (
                <SyncJobCard key={job.id} job={job} isActive={false} />
            ))}
        </div>
    )
}
```

**Deliverables:**
- ✅ Automated hourly sync scheduling
- ✅ Real-time sync progress monitoring
- ✅ Job status tracking and history
- ✅ Error handling and alerting
- ✅ Live dashboard updates

### Phase 5: Custom Dashboard (Optional - Week 4)

#### 5.1 Next.js Dashboard Setup
```bash
# Create dashboard project
npx create-next-app@latest canvas-dashboard --typescript --tailwind --app

# Install Supabase client
npm install @supabase/supabase-js
npm install @supabase/auth-helpers-nextjs
```

#### 5.2 Dashboard Components
```typescript
// components/CourseGrid.tsx
export function CourseGrid({ courses }) {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {courses.map(course => (
                <CourseCard key={course.id} course={course} />
            ))}
        </div>
    )
}

// components/ContentSearch.tsx
export function ContentSearch() {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    
    const searchContent = async (searchQuery: string) => {
        const { data } = await supabase
            .from('content_extractions')
            .select('original_title, text_preview, courses(name)')
            .textSearch('extracted_text', searchQuery)
            .limit(20)
        
        setResults(data)
    }
    
    return (
        <div className="search-interface">
            <SearchInput 
                value={query}
                onChange={setQuery}
                onSearch={searchContent}
            />
            <SearchResults results={results} />
        </div>
    )
}
```

**Deliverables:**
- ✅ Professional custom dashboard
- ✅ Course overview and navigation
- ✅ Full-text content search
- ✅ Real-time sync monitoring
- ✅ Analytics and insights
- ✅ Mobile-responsive design

## 🔄 Migration from Current System

### Step 1: Parallel Setup
```python
# Keep existing system running while setting up Supabase
class HybridCanvasClient(CanvasClient):
    def __init__(self, enable_supabase=False):
        super().__init__()
        self.supabase_enabled = enable_supabase
        if enable_supabase:
            self.supabase = create_client(...)
    
    async def get_active_courses(self):
        courses = await super().get_active_courses()
        
        if self.supabase_enabled:
            # Also store in Supabase
            await self._store_courses_in_supabase(courses)
        
        return courses
```

### Step 2: Gradual Feature Migration
```python
# Feature flags for gradual migration
FEATURES = {
    'STORE_IN_SUPABASE': True,      # Phase 1
    'EXTRACT_TEXT': True,           # Phase 2  
    'REAL_TIME_UPDATES': True,      # Phase 3
    'CUSTOM_DASHBOARD': False       # Phase 4 (optional)
}
```

### Step 3: Data Validation
```python
# Validate data consistency between systems
async def validate_migration():
    """Ensure Supabase data matches existing system."""
    
    courses_local = await get_courses_from_current_system()
    courses_supabase = supabase.table('courses').select('*').execute()
    
    assert len(courses_local) == len(courses_supabase.data)
    
    for local_course in courses_local:
        supabase_course = find_course_by_id(courses_supabase.data, local_course['id'])
        assert supabase_course is not None
        assert supabase_course['name'] == local_course['name']
```

## 🎯 Success Metrics

### Technical Metrics
- **Setup Time**: <1 day for database and basic functionality
- **Sync Performance**: Same performance as PostgreSQL version
- **UI Availability**: Immediate data viewing capability
- **Real-time Updates**: <1 second latency for live updates
- **Search Performance**: <100ms for full-text searches

### Operational Benefits
- **Zero Database Administration**: No PostgreSQL management needed
- **Automatic Backups**: Built-in point-in-time recovery
- **Instant APIs**: No backend development required
- **Real-time by Default**: Live updates without complex setup
- **Global Performance**: CDN-backed database access

### Cost Analysis
```typescript
// Monthly cost comparison
const costs = {
    supabase_free: "$0/month",        // Your usage fits in free tier
    postgres_aws: "$25-50/month",     // RDS + EC2 costs
    development_time: "50% faster",   // Estimated time savings
    maintenance_effort: "90% less"    // No database administration
}
```

## 🚀 Quick Start Guide

### 1. Create Supabase Project (5 minutes)
1. Go to [supabase.com](https://supabase.com)
2. Create account and new project
3. Copy project URL and anon key

### 2. Setup Schema (10 minutes)
```bash
# Clone your existing project
git clone your-canvas-scraper

# Install Supabase dependencies
pip install supabase

# Setup environment
cp .env.example .env
# Add Supabase credentials to .env

# Run schema setup
python scripts/setup_supabase_schema.py
```

### 3. Test Basic Functionality (15 minutes)
```python
# Test Supabase connection
from supabase import create_client
supabase = create_client(url, key)

# Test data insertion
result = supabase.table('courses').insert({
    'id': 12345,
    'name': 'Test Course',
    'enrollment_state': 'active'
}).execute()

print("✅ Supabase integration working!")
```

### 4. Access Dashboard (Immediate)
1. Go to your Supabase project dashboard
2. Click "Table Editor"
3. Browse your data immediately!

## 🎉 Recommendation: **YES, Use Supabase!**

**Supabase is perfect for your Canvas scraper project because:**

✅ **Instant UI**: Built-in dashboard for immediate data viewing
✅ **Real-time Updates**: See sync progress and new content live  
✅ **Zero Setup Time**: Database + APIs + UI in minutes
✅ **Cost Effective**: Free tier covers your entire use case
✅ **Same Schema**: Your existing PostgreSQL schema works perfectly
✅ **Professional Features**: Authentication, APIs, storage included
✅ **Scalable**: Grows with your needs automatically
✅ **Low Maintenance**: Managed service with automatic updates

The combination of sophisticated text extraction, intelligent sync, and instant UI capabilities makes this a powerful solution that's both developer-friendly and user-friendly.