-- Quick Supabase Setup for Canvas Scraper
-- Copy and paste this into your Supabase SQL Editor

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core table for courses
CREATE TABLE IF NOT EXISTS courses (
    id BIGINT PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    course_code VARCHAR(100),
    enrollment_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP WITH TIME ZONE
);

-- Core table for extracted content
CREATE TABLE IF NOT EXISTS content_extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    
    -- Original content metadata
    original_title VARCHAR(500),
    original_content_type VARCHAR(100),
    original_file_size BIGINT,
    
    -- Extraction results
    extracted_text TEXT,
    text_preview TEXT,
    extraction_method VARCHAR(50),
    extraction_status VARCHAR(50) DEFAULT 'pending',
    
    -- Content analysis
    character_count INTEGER,
    word_count INTEGER,
    
    -- Content hash for change detection
    content_hash VARCHAR(64),
    text_hash VARCHAR(64),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    extracted_at TIMESTAMP WITH TIME ZONE,
    
    -- Unique constraint to prevent duplicates
    UNIQUE(source_type, source_id, course_id)
);

-- Table for sync jobs tracking
CREATE TABLE IF NOT EXISTS sync_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    course_id BIGINT REFERENCES courses(id),
    
    -- Progress tracking
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Results
    result_summary JSONB,
    error_log TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_courses_updated_at ON courses(updated_at);
CREATE INDEX IF NOT EXISTS idx_extractions_course ON content_extractions(course_id);
CREATE INDEX IF NOT EXISTS idx_extractions_status ON content_extractions(extraction_status);
CREATE INDEX IF NOT EXISTS idx_extractions_hash ON content_extractions(content_hash);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status);

-- Enable Row Level Security (RLS) for multi-user access
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_jobs ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations for now (you can restrict later)
CREATE POLICY "Enable all operations for authenticated users" ON courses
    FOR ALL USING (true);

CREATE POLICY "Enable all operations for authenticated users" ON content_extractions
    FOR ALL USING (true);

CREATE POLICY "Enable all operations for authenticated users" ON sync_jobs
    FOR ALL USING (true);

-- Function to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers
CREATE TRIGGER update_courses_updated_at 
    BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_extractions_updated_at 
    BEFORE UPDATE ON content_extractions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();