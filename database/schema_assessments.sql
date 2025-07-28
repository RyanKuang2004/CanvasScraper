-- =====================================================
-- CANVAS SCRAPER: SIMPLIFIED ASSESSMENTS SCHEMA
-- =====================================================
-- Essential fields only for assignments and quizzes
-- Compatible with Supabase PostgreSQL

-- =====================================================
-- MAIN ASSESSMENTS TABLE
-- =====================================================

CREATE TABLE course_assessments (
    id BIGINT PRIMARY KEY,                    -- Canvas assignment/quiz ID
    course_id BIGINT NOT NULL,                -- Course identifier
    type VARCHAR(20) NOT NULL CHECK (type IN ('assignment', 'quiz')),
    
    -- Essential Information
    name VARCHAR(500) NOT NULL,               -- Assignment/quiz title
    description TEXT,                         -- Main content (HTML converted to text)
    due_at TIMESTAMP WITH TIME ZONE,          -- Due date and time
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Index for filtering by course
CREATE INDEX idx_course_assessments_course_id ON course_assessments(course_id);

-- Index for filtering by type
CREATE INDEX idx_course_assessments_type ON course_assessments(type);

-- Index for due date queries (only where due_at is not null)
CREATE INDEX idx_course_assessments_due_at ON course_assessments(due_at) WHERE due_at IS NOT NULL;

-- Composite index for common queries (course + due date)
CREATE INDEX idx_assessments_course_due ON course_assessments(course_id, due_at);

-- =====================================================
-- AUTOMATIC TIMESTAMP UPDATES
-- =====================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at on row changes
CREATE TRIGGER update_course_assessments_updated_at
    BEFORE UPDATE ON course_assessments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- HELPFUL VIEWS
-- =====================================================

-- View for upcoming assessments (due in the future)
CREATE VIEW upcoming_assessments AS
SELECT 
    *,
    EXTRACT(EPOCH FROM (due_at - CURRENT_TIMESTAMP))/86400 as days_until_due
FROM course_assessments
WHERE 
    due_at IS NOT NULL 
    AND due_at > CURRENT_TIMESTAMP
ORDER BY due_at ASC;

-- View for overdue assessments
CREATE VIEW overdue_assessments AS
SELECT 
    *,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - due_at))/86400 as days_overdue
FROM course_assessments
WHERE 
    due_at IS NOT NULL 
    AND due_at < CURRENT_TIMESTAMP
ORDER BY due_at DESC;

-- =====================================================
-- SAMPLE DATA INSERT (for testing)
-- =====================================================

-- Example: Insert a sample assignment
-- INSERT INTO course_assessments (id, course_id, type, name, description, due_at)
-- VALUES (
--     12345,
--     213007,
--     'assignment',
--     'Final Project Report',
--     'Submit your final project report including methodology, results, and conclusions.',
--     '2024-12-15 23:59:00+00'
-- );

-- =====================================================
-- SAMPLE QUERIES
-- =====================================================

-- Get all assignments for a specific course:
-- SELECT * FROM course_assessments WHERE course_id = 213007 AND type = 'assignment';

-- Get all upcoming assessments due within 7 days:
-- SELECT * FROM upcoming_assessments WHERE days_until_due <= 7;

-- Get all overdue assessments:
-- SELECT * FROM overdue_assessments;

-- Search assessments by name or description:
-- SELECT * FROM course_assessments WHERE name ILIKE '%final%' OR description ILIKE '%project%';

-- =====================================================
-- TABLE COMMENTS
-- =====================================================

COMMENT ON TABLE course_assessments IS 'Simplified storage for Canvas assignments and quizzes with essential fields only';
COMMENT ON COLUMN course_assessments.id IS 'Canvas assignment or quiz ID (from Canvas API)';
COMMENT ON COLUMN course_assessments.course_id IS 'Canvas course ID that contains this assessment';
COMMENT ON COLUMN course_assessments.type IS 'Type of assessment: assignment or quiz';
COMMENT ON COLUMN course_assessments.name IS 'Title/name of the assignment or quiz';
COMMENT ON COLUMN course_assessments.description IS 'Main content/instructions (converted from HTML to plain text)';
COMMENT ON COLUMN course_assessments.due_at IS 'Due date and time (with timezone support)';