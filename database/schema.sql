-- Canvas Scraper Enhanced Database Schema
-- PostgreSQL 13+ with full-text search capabilities

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create schema for better organization
CREATE SCHEMA IF NOT EXISTS canvas_scraper;
SET search_path TO canvas_scraper, public;

-- =====================================================
-- CORE ENTITIES
-- =====================================================

-- Institutions/Canvas instances
CREATE TABLE institutions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    canvas_url VARCHAR(500) NOT NULL UNIQUE,
    api_version VARCHAR(10) DEFAULT 'v1',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Courses from Canvas
CREATE TABLE courses (
    id BIGINT PRIMARY KEY, -- Canvas course ID
    institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    course_code VARCHAR(100),
    term VARCHAR(100),
    enrollment_state VARCHAR(50),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP WITH TIME ZONE,
    canvas_updated_at TIMESTAMP WITH TIME ZONE
);

-- Modules within courses
CREATE TABLE modules (
    id BIGINT PRIMARY KEY, -- Canvas module ID
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    position INTEGER,
    workflow_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    canvas_updated_at TIMESTAMP WITH TIME ZONE
);

-- Module items (pages, files, assignments, etc.)
CREATE TABLE module_items (
    id BIGINT PRIMARY KEY, -- Canvas module item ID
    module_id BIGINT REFERENCES modules(id) ON DELETE CASCADE,
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    type VARCHAR(50) NOT NULL, -- Page, File, Assignment, Quiz, etc.
    content_id BIGINT, -- ID of the actual content (page_id, file_id, etc.)
    url VARCHAR(1000),
    external_url VARCHAR(1000),
    position INTEGER,
    indent INTEGER DEFAULT 0,
    workflow_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    canvas_updated_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- CONTENT STORAGE
-- =====================================================

-- Files from Canvas (PDFs, PPTX, DOCX, etc.)
CREATE TABLE files (
    id BIGINT PRIMARY KEY, -- Canvas file ID
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    folder_id BIGINT,
    filename VARCHAR(500) NOT NULL,
    display_name VARCHAR(500),
    content_type VARCHAR(100),
    file_size BIGINT,
    url VARCHAR(1000),
    download_url VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    canvas_updated_at TIMESTAMP WITH TIME ZONE,
    canvas_created_at TIMESTAMP WITH TIME ZONE
);

-- Pages from Canvas
CREATE TABLE pages (
    id BIGINT, -- Canvas page ID (not always unique across courses)
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL, -- Canvas page URL slug
    title VARCHAR(500) NOT NULL,
    body TEXT,
    workflow_state VARCHAR(50),
    editing_roles VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    canvas_updated_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (course_id, url) -- Composite key since page IDs aren't globally unique
);

-- Assignments from Canvas
CREATE TABLE assignments (
    id BIGINT PRIMARY KEY, -- Canvas assignment ID
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    due_at TIMESTAMP WITH TIME ZONE,
    unlock_at TIMESTAMP WITH TIME ZONE,
    lock_at TIMESTAMP WITH TIME ZONE,
    points_possible DECIMAL(8,2),
    submission_types TEXT[], -- Array of submission types
    workflow_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    canvas_updated_at TIMESTAMP WITH TIME ZONE
);

-- Quizzes from Canvas
CREATE TABLE quizzes (
    id BIGINT PRIMARY KEY, -- Canvas quiz ID
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    due_at TIMESTAMP WITH TIME ZONE,
    lock_at TIMESTAMP WITH TIME ZONE,
    unlock_at TIMESTAMP WITH TIME ZONE,
    points_possible DECIMAL(8,2),
    time_limit INTEGER, -- minutes
    quiz_type VARCHAR(50),
    workflow_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    canvas_updated_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- TEXT EXTRACTION & PROCESSING
-- =====================================================

-- Extracted text content with metadata
CREATE TABLE content_extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL, -- 'file', 'page', 'assignment', 'quiz'
    source_id VARCHAR(100) NOT NULL, -- Could be file_id, page composite key, etc.
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    
    -- Original content metadata
    original_title VARCHAR(500),
    original_url VARCHAR(1000),
    original_content_type VARCHAR(100),
    original_file_size BIGINT,
    
    -- Extraction results
    extracted_text TEXT,
    text_preview TEXT, -- First 500 chars for quick preview
    extraction_method VARCHAR(50), -- 'pypdf2', 'pdfplumber', 'python-pptx', etc.
    extraction_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'success', 'failed', 'skipped'
    extraction_error TEXT,
    
    -- Content analysis
    character_count INTEGER,
    word_count INTEGER,
    language_detected VARCHAR(10),
    
    -- Search vector for full-text search
    search_vector tsvector,
    
    -- Content hash for change detection
    content_hash VARCHAR(64), -- SHA-256 hash of original content
    text_hash VARCHAR(64), -- SHA-256 hash of extracted text
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    extracted_at TIMESTAMP WITH TIME ZONE,
    
    -- Unique constraint to prevent duplicates
    UNIQUE(source_type, source_id, course_id)
);

-- =====================================================
-- SYNC MANAGEMENT
-- =====================================================

-- Track synchronization state and progress
CREATE TABLE sync_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL, -- 'full_sync', 'incremental_sync', 'course_sync'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    
    -- Scope of the sync job
    institution_id UUID REFERENCES institutions(id),
    course_id BIGINT REFERENCES courses(id),
    
    -- Progress tracking
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Results and errors
    result_summary JSONB, -- Statistics about what was processed
    error_log TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Track last successful sync for each course
CREATE TABLE course_sync_state (
    course_id BIGINT PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
    last_full_sync_at TIMESTAMP WITH TIME ZONE,
    last_incremental_sync_at TIMESTAMP WITH TIME ZONE,
    last_successful_sync_at TIMESTAMP WITH TIME ZONE,
    sync_errors INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    
    -- Sync metadata
    last_sync_job_id UUID REFERENCES sync_jobs(id),
    items_count INTEGER DEFAULT 0,
    extracted_content_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- CHANGE TRACKING
-- =====================================================

-- Track changes to content for incremental updates
CREATE TABLE content_changes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    change_type VARCHAR(50) NOT NULL, -- 'created', 'updated', 'deleted'
    
    -- What changed
    entity_type VARCHAR(50) NOT NULL, -- 'course', 'module', 'module_item', 'file', 'page', etc.
    entity_id VARCHAR(100) NOT NULL,
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    
    -- Change details
    old_hash VARCHAR(64),
    new_hash VARCHAR(64),
    change_summary JSONB,
    
    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    processing_error TEXT,
    
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Course indexes
CREATE INDEX idx_courses_institution ON courses(institution_id);
CREATE INDEX idx_courses_updated_at ON courses(canvas_updated_at);
CREATE INDEX idx_courses_last_synced ON courses(last_synced_at);

-- Module indexes
CREATE INDEX idx_modules_course ON modules(course_id);
CREATE INDEX idx_modules_updated_at ON modules(canvas_updated_at);

-- Module item indexes
CREATE INDEX idx_module_items_module ON module_items(module_id);
CREATE INDEX idx_module_items_course ON module_items(course_id);
CREATE INDEX idx_module_items_type ON module_items(type);
CREATE INDEX idx_module_items_content ON module_items(type, content_id);

-- File indexes
CREATE INDEX idx_files_course ON files(course_id);
CREATE INDEX idx_files_content_type ON files(content_type);
CREATE INDEX idx_files_updated_at ON files(canvas_updated_at);

-- Page indexes
CREATE INDEX idx_pages_course ON pages(course_id);
CREATE INDEX idx_pages_updated_at ON pages(canvas_updated_at);

-- Content extraction indexes
CREATE INDEX idx_extractions_source ON content_extractions(source_type, source_id);
CREATE INDEX idx_extractions_course ON content_extractions(course_id);
CREATE INDEX idx_extractions_status ON content_extractions(extraction_status);
CREATE INDEX idx_extractions_hash ON content_extractions(content_hash);
CREATE INDEX idx_extractions_search ON content_extractions USING GIN(search_vector);

-- Full-text search index
CREATE INDEX idx_extractions_text_search ON content_extractions USING GIN(to_tsvector('english', coalesce(extracted_text, '')));

-- Sync job indexes
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);
CREATE INDEX idx_sync_jobs_type ON sync_jobs(job_type);
CREATE INDEX idx_sync_jobs_started ON sync_jobs(started_at);

-- Change tracking indexes
CREATE INDEX idx_content_changes_processed ON content_changes(processed);
CREATE INDEX idx_content_changes_entity ON content_changes(entity_type, entity_id);
CREATE INDEX idx_content_changes_course ON content_changes(course_id);

-- =====================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- =====================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers to relevant tables
CREATE TRIGGER update_institutions_updated_at BEFORE UPDATE ON institutions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_modules_updated_at BEFORE UPDATE ON modules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_module_items_updated_at BEFORE UPDATE ON module_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_files_updated_at BEFORE UPDATE ON files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pages_updated_at BEFORE UPDATE ON pages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_extractions_updated_at BEFORE UPDATE ON content_extractions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_course_sync_state_updated_at BEFORE UPDATE ON course_sync_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to automatically update search vector
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector = to_tsvector('english', 
        coalesce(NEW.original_title, '') || ' ' || 
        coalesce(NEW.extracted_text, '')
    );
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to update search vector on content extraction changes
CREATE TRIGGER update_content_search_vector 
    BEFORE INSERT OR UPDATE ON content_extractions
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- View combining content with extraction status
CREATE VIEW content_with_extractions AS
SELECT 
    mi.id as module_item_id,
    mi.title,
    mi.type as content_type,
    mi.course_id,
    c.name as course_name,
    ce.id as extraction_id,
    ce.extraction_status,
    ce.text_preview,
    ce.word_count,
    ce.extracted_at,
    ce.extraction_error
FROM module_items mi
JOIN courses c ON mi.course_id = c.id
LEFT JOIN content_extractions ce ON 
    ce.source_type = LOWER(mi.type) AND 
    ce.source_id = mi.content_id::TEXT AND
    ce.course_id = mi.course_id;

-- View for sync status summary
CREATE VIEW sync_status_summary AS
SELECT 
    c.id as course_id,
    c.name as course_name,
    css.last_successful_sync_at,
    css.consecutive_failures,
    css.items_count,
    css.extracted_content_count,
    CASE 
        WHEN css.last_successful_sync_at IS NULL THEN 'never_synced'
        WHEN css.last_successful_sync_at < NOW() - INTERVAL '2 hours' THEN 'overdue'
        WHEN css.consecutive_failures > 0 THEN 'failing'
        ELSE 'healthy'
    END as sync_health
FROM courses c
LEFT JOIN course_sync_state css ON c.id = css.course_id;

-- =====================================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- =====================================================

-- Function to get content that needs extraction
CREATE OR REPLACE FUNCTION get_content_needing_extraction(p_course_id BIGINT DEFAULT NULL)
RETURNS TABLE(
    source_type VARCHAR(50),
    source_id VARCHAR(100),
    course_id BIGINT,
    title VARCHAR(500),
    url VARCHAR(1000)
) AS $$
BEGIN
    RETURN QUERY
    -- Files that need extraction
    SELECT 
        'file'::VARCHAR(50),
        f.id::VARCHAR(100),
        f.course_id,
        f.display_name,
        f.download_url
    FROM files f
    LEFT JOIN content_extractions ce ON 
        ce.source_type = 'file' AND 
        ce.source_id = f.id::TEXT AND
        ce.course_id = f.course_id
    WHERE 
        ce.id IS NULL 
        AND f.content_type IN ('application/pdf', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        AND (p_course_id IS NULL OR f.course_id = p_course_id)
    
    UNION ALL
    
    -- Pages that need extraction
    SELECT 
        'page'::VARCHAR(50),
        p.course_id::TEXT || ':' || p.url,
        p.course_id,
        p.title,
        NULL::VARCHAR(1000)
    FROM pages p
    LEFT JOIN content_extractions ce ON 
        ce.source_type = 'page' AND 
        ce.source_id = p.course_id::TEXT || ':' || p.url AND
        ce.course_id = p.course_id
    WHERE 
        ce.id IS NULL 
        AND p.body IS NOT NULL
        AND (p_course_id IS NULL OR p.course_id = p_course_id);
END;
$$ LANGUAGE plpgsql;