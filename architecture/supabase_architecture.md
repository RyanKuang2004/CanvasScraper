# Supabase-Enhanced Canvas Scraper Architecture

## Architecture Overview

The Supabase integration transforms the Canvas scraper into a modern, cloud-native application with instant UI capabilities and managed database services.

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Canvas LMS    │    │  Canvas Scraper  │    │    Supabase     │
│                 │◄───┤   Enhanced       ├───►│   PostgreSQL    │
│ • Pages         │    │                  │    │   + Dashboard   │
│ • PDF Files     │    │ • Text Extractor │    │                 │
│ • PPTX Files    │    │ • Sync Engine    │    │ • Auto APIs     │
│ • DOCX Files    │    │ • Supabase Client│    │ • Real-time     │
└─────────────────┘    └──────────────────┘    │ • Auth          │
                                │               │ • Storage       │
                                ▼               └─────────────────┘
                       ┌─────────────────┐              │
                       │  Custom UI      │◄─────────────┘
                       │  Dashboard      │
                       │                 │
                       │ • Course View   │
                       │ • Content Search│
                       │ • Sync Monitor  │
                       │ • Analytics     │
                       └─────────────────┘
```

## Key Components

### 1. Supabase Database Layer
```typescript
// Connection configuration
const supabaseUrl = 'https://your-project.supabase.co'
const supabaseKey = 'your-anon-key'
const supabase = createClient(supabaseUrl, supabaseKey)

// The same PostgreSQL schema works with Supabase!
// All tables: institutions, courses, modules, content_extractions, etc.
```

### 2. Enhanced Canvas Client with Supabase
```python
# src/canvas/supabase_client.py
import asyncio
from supabase import create_client, Client
from postgrest import APIError

class SupabaseCanvasClient(CanvasClient):
    def __init__(self, supabase_url: str, supabase_key: str):
        super().__init__()
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    async def store_extracted_content(self, extraction: ContentExtraction):
        """Store extracted content in Supabase with real-time updates."""
        try:
            result = self.supabase.table('content_extractions').insert({
                'source_type': extraction.source_type,
                'source_id': extraction.source_id,
                'course_id': extraction.course_id,
                'extracted_text': extraction.text,
                'original_title': extraction.title,
                'extraction_method': extraction.method,
                'character_count': len(extraction.text),
                'word_count': len(extraction.text.split()),
                'content_hash': extraction.content_hash
            }).execute()
            
            # Automatic real-time updates to connected UIs!
            return result
            
        except APIError as e:
            if 'duplicate key' in str(e):
                # Handle deduplication gracefully
                return await self._update_existing_content(extraction)
            raise
    
    async def get_course_content(self, course_id: int):
        """Retrieve all content for a course with rich filtering."""
        return self.supabase.table('content_extractions') \
            .select('*, courses(name)') \
            .eq('course_id', course_id) \
            .order('extracted_at', desc=True) \
            .execute()
    
    async def search_content(self, query: str, course_id: int = None):
        """Full-text search across all extracted content."""
        search_query = self.supabase.table('content_extractions') \
            .select('original_title, text_preview, course_id, courses(name)') \
            .text_search('extracted_text', query)
        
        if course_id:
            search_query = search_query.eq('course_id', course_id)
        
        return search_query.execute()
```

### 3. Real-time Sync Monitoring
```python
# Real-time sync progress updates
async def setup_realtime_sync_updates(self):
    """Setup real-time updates for sync progress."""
    
    def handle_sync_update(payload):
        """Handle real-time sync job updates."""
        job_data = payload['new']
        print(f"Sync job {job_data['id']} status: {job_data['status']}")
        
        # Update UI in real-time
        self.broadcast_sync_status(job_data)
    
    # Subscribe to sync_jobs table changes
    self.supabase.table('sync_jobs') \
        .on('UPDATE', handle_sync_update) \
        .subscribe()
```

### 4. Row-Level Security (RLS)
```sql
-- Enable RLS for multi-tenant security
ALTER TABLE content_extractions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see content from their institution
CREATE POLICY "Users can view own institution content" ON content_extractions
    FOR SELECT USING (
        course_id IN (
            SELECT id FROM courses 
            WHERE institution_id = (
                SELECT institution_id FROM user_institutions 
                WHERE user_id = auth.uid()
            )
        )
    );
```

## Dashboard UI Options

### Option 1: Supabase Built-in Dashboard

**Immediate Benefits:**
- **Zero Setup**: Available immediately after database creation
- **Full CRUD**: Create, read, update, delete any data
- **SQL Editor**: Run complex queries with syntax highlighting
- **Real-time Updates**: See data changes live
- **Export Functions**: Download data in various formats

**Perfect for:**
- Development and debugging
- Admin tasks and data management
- Quick data analysis
- Content verification

### Option 2: Custom Next.js Dashboard

**Architecture:**
```typescript
// pages/dashboard.tsx
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Dashboard() {
    const [courses, setCourses] = useState([])
    const [recentContent, setRecentContent] = useState([])
    
    useEffect(() => {
        // Load initial data
        loadDashboardData()
        
        // Setup real-time subscriptions
        const subscription = supabase
            .from('content_extractions')
            .on('INSERT', payload => {
                setRecentContent(prev => [payload.new, ...prev.slice(0, 9)])
            })
            .subscribe()
        
        return () => subscription.unsubscribe()
    }, [])
    
    return (
        <div className="dashboard">
            <CourseGrid courses={courses} />
            <RecentContent content={recentContent} />
            <SearchInterface />
            <SyncMonitor />
        </div>
    )
}
```

**Features:**
- **Course Overview**: Visual cards for each course
- **Content Search**: Full-text search with highlighting
- **Sync Monitoring**: Real-time sync progress
- **Analytics**: Content statistics and trends
- **Mobile Responsive**: Works on all devices

### Option 3: No-Code Dashboard (Retool)

**Setup Time:** 30 minutes
**Features:**
- Drag-and-drop interface builder
- Direct Supabase connection
- Rich visualizations and charts
- Custom workflows and automation
- User authentication integration

## Migration from PostgreSQL Schema

**Good News:** The existing schema works perfectly with Supabase!

```python
# Migration script
async def migrate_to_supabase():
    """Migrate existing PostgreSQL schema to Supabase."""
    
    # 1. Create tables in Supabase (same SQL schema)
    with open('database/schema.sql', 'r') as f:
        schema_sql = f.read()
    
    # Execute schema creation
    supabase.rpc('exec_sql', {'sql': schema_sql})
    
    # 2. If migrating existing data
    if has_existing_data():
        await migrate_existing_data()
    
    # 3. Setup Row-Level Security
    await setup_rls_policies()
    
    # 4. Configure real-time subscriptions
    await enable_realtime_tables()

async def enable_realtime_tables():
    """Enable real-time updates for key tables."""
    tables = [
        'content_extractions',
        'sync_jobs', 
        'courses',
        'content_changes'
    ]
    
    for table in tables:
        supabase.rpc('enable_realtime', {'table_name': table})
```

## Advantages of Supabase for This Project

### Development Speed
- **10x Faster Setup**: Database + API + Dashboard in minutes
- **Auto-Generated APIs**: No backend coding needed
- **Built-in Authentication**: User management included
- **Real-time by Default**: Live updates without WebSocket setup

### Operational Benefits
- **Managed Service**: No database administration
- **Automatic Backups**: Point-in-time recovery
- **Monitoring Included**: Performance dashboards
- **Global CDN**: Fast response times worldwide

### Cost Effectiveness
- **Free Tier**: 500MB database, 2GB bandwidth
- **Predictable Pricing**: $25/month for Pro features
- **No Infrastructure Costs**: No EC2/RDS management
- **Built-in Features**: Authentication, storage, APIs included

### Scalability
- **Automatic Scaling**: Handle traffic spikes
- **Connection Pooling**: Efficient database connections
- **Edge Functions**: Serverless compute when needed
- **Global Distribution**: Multi-region deployment

## Implementation Considerations

### Data Volume Planning
```typescript
// Estimate for Canvas scraper usage
const estimates = {
    courses: 50,                    // Typical student course load
    filesPerCourse: 100,           // Average files per course
    avgFileSize: "2MB",            // PDF/PPTX average size
    extractedTextPerFile: "10KB",  // Typical extracted text size
    totalStorage: "~50MB"          // Well within free tier
}
```

### Performance Optimization
```sql
-- Optimize for common queries
CREATE INDEX idx_content_search 
ON content_extractions USING GIN(to_tsvector('english', extracted_text));

CREATE INDEX idx_course_recent_content 
ON content_extractions(course_id, extracted_at DESC);
```

### Security Best Practices
```typescript
// Environment configuration
const supabaseConfig = {
    url: process.env.NEXT_PUBLIC_SUPABASE_URL,
    anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    serviceKey: process.env.SUPABASE_SERVICE_KEY // Server-side only
}

// Use service key for Canvas scraper backend
// Use anon key for frontend dashboard
```

This Supabase architecture provides immediate UI capabilities while maintaining all the sophisticated features of the original design - text extraction, incremental sync, deduplication, and automated scheduling.