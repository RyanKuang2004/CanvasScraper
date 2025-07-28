-- Supabase Schema for Canvas Content Storage
-- Enhanced schema with full-text search, indexing, and real-time capabilities

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Courses table
CREATE TABLE IF NOT EXISTS courses (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    canvas_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    code TEXT,
    term TEXT,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    enrollment_term_id INTEGER,
    workflow_state TEXT,
    course_format TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    is_public_to_auth_users BOOLEAN DEFAULT FALSE,
    public_syllabus BOOLEAN DEFAULT FALSE,
    public_syllabus_to_auth BOOLEAN DEFAULT FALSE,
    public_description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Modules table
CREATE TABLE IF NOT EXISTS modules (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    canvas_id TEXT UNIQUE NOT NULL,
    course_canvas_id TEXT NOT NULL REFERENCES courses(canvas_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER,
    unlock_at TIMESTAMPTZ,
    require_sequential_progress BOOLEAN DEFAULT FALSE,
    prerequisite_module_ids JSONB DEFAULT '[]',
    state TEXT,
    completed_at TIMESTAMPTZ,
    items_count INTEGER DEFAULT 0,
    items_url TEXT,
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- File contents table (metadata about processed files)
CREATE TABLE IF NOT EXISTS file_contents (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    canvas_id TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    content_fingerprint TEXT,
    file_size BIGINT DEFAULT 0,
    content_type TEXT DEFAULT 'unknown',
    extraction_method TEXT,
    processing_time_ms INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    success BOOLEAN DEFAULT FALSE,
    was_cached BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    
    -- File metadata
    page_count INTEGER,
    word_count INTEGER,
    character_count INTEGER,
    language TEXT,
    author TEXT,
    title TEXT,
    subject TEXT,
    creation_date TIMESTAMPTZ,
    keywords JSONB DEFAULT '[]',
    has_images BOOLEAN DEFAULT FALSE,
    has_tables BOOLEAN DEFAULT FALSE,
    errors JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content texts table (full extracted text)
CREATE TABLE IF NOT EXISTS content_texts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    file_canvas_id TEXT UNIQUE NOT NULL REFERENCES file_contents(canvas_id) ON DELETE CASCADE,
    full_text TEXT NOT NULL,
    content_hash TEXT,
    structured_content JSONB,
    
    -- Full-text search vector
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(full_text, '')), 'A')
    ) STORED,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content chunks table (chunked text for embedding/retrieval)
CREATE TABLE IF NOT EXISTS content_chunks (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    chunk_id TEXT UNIQUE NOT NULL,
    file_canvas_id TEXT NOT NULL REFERENCES file_contents(canvas_id) ON DELETE CASCADE,
    source_file_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    
    -- Chunk content
    content TEXT NOT NULL,
    content_hash TEXT,
    
    -- Position information
    char_start INTEGER,
    char_end INTEGER,
    token_count INTEGER DEFAULT 0,
    
    -- Structure information
    section_title TEXT,
    page_number INTEGER,
    slide_number INTEGER,
    heading_level INTEGER,
    
    -- Metadata (JSON containing course_id, module_id, etc.)
    metadata JSONB DEFAULT '{}',
    
    -- Full-text search vector
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(content, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(section_title, '')), 'B')
    ) STORED,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Processing state tracking table
CREATE TABLE IF NOT EXISTS processing_state (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    entity_type TEXT NOT NULL, -- 'file', 'module', 'course'
    entity_id TEXT NOT NULL,
    fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_metadata JSONB DEFAULT '{}',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(entity_type, entity_id)
);

-- Embeddings table (for vector search - optional advanced feature)
CREATE TABLE IF NOT EXISTS content_embeddings (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    chunk_id TEXT NOT NULL REFERENCES content_chunks(chunk_id) ON DELETE CASCADE,
    embedding_model TEXT NOT NULL DEFAULT 'text-embedding-ada-002',
    embedding_vector FLOAT8[] NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Search analytics table (track search queries)
CREATE TABLE IF NOT EXISTS search_analytics (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    query TEXT NOT NULL,
    course_id TEXT,
    results_count INTEGER DEFAULT 0,
    response_time_ms INTEGER DEFAULT 0,
    user_id TEXT,
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance

-- Courses indexes
CREATE INDEX IF NOT EXISTS idx_courses_canvas_id ON courses(canvas_id);
CREATE INDEX IF NOT EXISTS idx_courses_workflow_state ON courses(workflow_state);
CREATE INDEX IF NOT EXISTS idx_courses_term ON courses(term);

-- Modules indexes
CREATE INDEX IF NOT EXISTS idx_modules_canvas_id ON modules(canvas_id);
CREATE INDEX IF NOT EXISTS idx_modules_course_id ON modules(course_canvas_id);
CREATE INDEX IF NOT EXISTS idx_modules_position ON modules(position);

-- File contents indexes
CREATE INDEX IF NOT EXISTS idx_file_contents_canvas_id ON file_contents(canvas_id);
CREATE INDEX IF NOT EXISTS idx_file_contents_fingerprint ON file_contents(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_file_contents_content_type ON file_contents(content_type);
CREATE INDEX IF NOT EXISTS idx_file_contents_success ON file_contents(success);
CREATE INDEX IF NOT EXISTS idx_file_contents_created_at ON file_contents(created_at);

-- Content texts indexes
CREATE INDEX IF NOT EXISTS idx_content_texts_file_id ON content_texts(file_canvas_id);
CREATE INDEX IF NOT EXISTS idx_content_texts_search ON content_texts USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_content_texts_content_hash ON content_texts(content_hash);

-- Content chunks indexes
CREATE INDEX IF NOT EXISTS idx_content_chunks_chunk_id ON content_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_content_chunks_file_id ON content_chunks(file_canvas_id);
CREATE INDEX IF NOT EXISTS idx_content_chunks_source_file ON content_chunks(source_file_id);
CREATE INDEX IF NOT EXISTS idx_content_chunks_chunk_index ON content_chunks(chunk_index);
CREATE INDEX IF NOT EXISTS idx_content_chunks_search ON content_chunks USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_content_chunks_metadata ON content_chunks USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_content_chunks_section ON content_chunks(section_title);
CREATE INDEX IF NOT EXISTS idx_content_chunks_page ON content_chunks(page_number);

-- Processing state indexes
CREATE INDEX IF NOT EXISTS idx_processing_state_entity ON processing_state(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_processing_state_status ON processing_state(status);
CREATE INDEX IF NOT EXISTS idx_processing_state_fingerprint ON processing_state(fingerprint);
CREATE INDEX IF NOT EXISTS idx_processing_state_created_at ON processing_state(created_at);

-- Embeddings indexes (for vector search)
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON content_embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON content_embeddings(embedding_model);

-- Search analytics indexes
CREATE INDEX IF NOT EXISTS idx_search_analytics_query ON search_analytics USING GIN(to_tsvector('english', query));
CREATE INDEX IF NOT EXISTS idx_search_analytics_course_id ON search_analytics(course_id);
CREATE INDEX IF NOT EXISTS idx_search_analytics_created_at ON search_analytics(created_at);

-- Create functions for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_modules_updated_at BEFORE UPDATE ON modules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_file_contents_updated_at BEFORE UPDATE ON file_contents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_processing_state_updated_at BEFORE UPDATE ON processing_state FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create views for common queries

-- Course summary view
CREATE OR REPLACE VIEW course_summary AS
SELECT 
    c.canvas_id,
    c.name,
    c.code,
    c.term,
    c.workflow_state,
    COUNT(DISTINCT m.id) as module_count,
    COUNT(DISTINCT fc.id) as file_count,
    COUNT(DISTINCT cc.id) as chunk_count,
    SUM(cc.token_count) as total_tokens,
    MAX(fc.updated_at) as last_processed
FROM courses c
LEFT JOIN modules m ON c.canvas_id = m.course_canvas_id
LEFT JOIN file_contents fc ON fc.canvas_id LIKE c.canvas_id || '_%'
LEFT JOIN content_chunks cc ON cc.file_canvas_id = fc.canvas_id
GROUP BY c.canvas_id, c.name, c.code, c.term, c.workflow_state;

-- Processing status view
CREATE OR REPLACE VIEW processing_status AS
SELECT 
    entity_type,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'processing') as processing,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_processing_time_seconds
FROM processing_state
GROUP BY entity_type;

-- Search function for content
CREATE OR REPLACE FUNCTION search_content(
    search_query TEXT,
    course_filter TEXT DEFAULT NULL,
    result_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    chunk_id TEXT,
    content TEXT,
    section_title TEXT,
    page_number INTEGER,
    slide_number INTEGER,
    file_path TEXT,
    course_id TEXT,
    relevance_rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cc.chunk_id,
        cc.content,
        cc.section_title,
        cc.page_number,
        cc.slide_number,
        fc.file_path,
        cc.metadata->>'course_id' as course_id,
        ts_rank(cc.search_vector, plainto_tsquery('english', search_query)) as relevance_rank
    FROM content_chunks cc
    JOIN file_contents fc ON cc.file_canvas_id = fc.canvas_id
    WHERE cc.search_vector @@ plainto_tsquery('english', search_query)
    AND (course_filter IS NULL OR cc.metadata->>'course_id' = course_filter)
    ORDER BY relevance_rank DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get content by course
CREATE OR REPLACE FUNCTION get_course_content_summary(course_canvas_id TEXT)
RETURNS TABLE (
    total_files INTEGER,
    total_chunks INTEGER,
    total_tokens BIGINT,
    content_types TEXT[],
    last_updated TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT fc.canvas_id)::INTEGER as total_files,
        COUNT(DISTINCT cc.chunk_id)::INTEGER as total_chunks,
        SUM(cc.token_count)::BIGINT as total_tokens,
        ARRAY_AGG(DISTINCT fc.content_type) as content_types,
        MAX(fc.updated_at) as last_updated
    FROM file_contents fc
    LEFT JOIN content_chunks cc ON cc.file_canvas_id = fc.canvas_id
    WHERE cc.metadata->>'course_id' = course_canvas_id;
END;
$$ LANGUAGE plpgsql;

-- Row Level Security (RLS) policies
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_contents ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_texts ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_state ENABLE ROW LEVEL SECURITY;

-- Allow read access to authenticated users
CREATE POLICY "Allow read access for authenticated users" ON courses FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON modules FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON file_contents FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON content_texts FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON content_chunks FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON processing_state FOR SELECT TO authenticated USING (true);

-- Allow insert/update for service role
CREATE POLICY "Allow full access for service role" ON courses FOR ALL TO service_role USING (true);
CREATE POLICY "Allow full access for service role" ON modules FOR ALL TO service_role USING (true);
CREATE POLICY "Allow full access for service role" ON file_contents FOR ALL TO service_role USING (true);
CREATE POLICY "Allow full access for service role" ON content_texts FOR ALL TO service_role USING (true);
CREATE POLICY "Allow full access for service role" ON content_chunks FOR ALL TO service_role USING (true);
CREATE POLICY "Allow full access for service role" ON processing_state FOR ALL TO service_role USING (true);

-- Comments for documentation
COMMENT ON TABLE courses IS 'Canvas course information';
COMMENT ON TABLE modules IS 'Canvas course modules';
COMMENT ON TABLE file_contents IS 'Metadata about processed files from Canvas';
COMMENT ON TABLE content_texts IS 'Full extracted text content from files';
COMMENT ON TABLE content_chunks IS 'Chunked text content for retrieval and embedding';
COMMENT ON TABLE processing_state IS 'Track processing state for deduplication';
COMMENT ON TABLE content_embeddings IS 'Vector embeddings for semantic search';
COMMENT ON TABLE search_analytics IS 'Track search queries and performance';

COMMENT ON FUNCTION search_content IS 'Full-text search across all content chunks';
COMMENT ON FUNCTION get_course_content_summary IS 'Get summary statistics for a course';

-- Sample data insertion (for testing)
/*
INSERT INTO courses (canvas_id, name, code, term) VALUES 
('12345', 'Introduction to Computer Science', 'CS101', 'Semester 1 2024');

INSERT INTO modules (canvas_id, course_canvas_id, name, position) VALUES 
('mod_1', '12345', 'Week 1: Fundamentals', 1),
('mod_2', '12345', 'Week 2: Data Structures', 2);
*/