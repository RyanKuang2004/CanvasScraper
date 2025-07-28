# 📋 Supabase Schema Deployment Guide

## 🎯 Overview

This guide explains how to deploy the simplified assessments schema to your Supabase project using the SQL Editor in the Supabase dashboard.

## 📊 Schema Summary

The simplified schema includes only essential fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | BIGINT | Canvas assignment/quiz ID (Primary Key) |
| `course_id` | BIGINT | Course identifier |
| `type` | VARCHAR(20) | Either 'assignment' or 'quiz' |
| `name` | VARCHAR(500) | Assignment/quiz title |
| `description` | TEXT | Main content (HTML converted to text) |
| `due_at` | TIMESTAMP WITH TIME ZONE | Due date and time |
| `created_at` | TIMESTAMP WITH TIME ZONE | Record creation time |
| `updated_at` | TIMESTAMP WITH TIME ZONE | Last update time |

## 🚀 Step-by-Step Deployment

### Step 1: Access Supabase Dashboard
1. Go to [supabase.com](https://supabase.com)
2. Sign in to your account
3. Select your project (or create a new one)

### Step 2: Open SQL Editor
1. In the left sidebar, click **"SQL Editor"**
2. Click **"New Query"** to create a new SQL script

### Step 3: Deploy the Schema

#### Option 1: Copy-Paste Method (Recommended)
1. Copy the entire contents of `schema_assessments_simple.sql`
2. Paste it into the SQL Editor
3. Click **"Run"** button (or press Ctrl/Cmd + Enter)

#### Option 2: Section-by-Section Method (Safer for beginners)

**Step 3a: Create the Main Table**
```sql
CREATE TABLE course_assessments (
    id BIGINT PRIMARY KEY,
    course_id BIGINT NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('assignment', 'quiz')),
    name VARCHAR(500) NOT NULL,
    description TEXT,
    due_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```
Click **Run** and verify it shows "Success" ✅

**Step 3b: Add Performance Indexes**
```sql
CREATE INDEX idx_course_assessments_course_id ON course_assessments(course_id);
CREATE INDEX idx_course_assessments_type ON course_assessments(type);
CREATE INDEX idx_course_assessments_due_at ON course_assessments(due_at) WHERE due_at IS NOT NULL;
CREATE INDEX idx_assessments_course_due ON course_assessments(course_id, due_at);
```
Click **Run** and verify success ✅

**Step 3c: Add Automatic Timestamp Updates**
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_course_assessments_updated_at
    BEFORE UPDATE ON course_assessments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```
Click **Run** and verify success ✅

**Step 3d: Add Helpful Views**
```sql
CREATE VIEW upcoming_assessments AS
SELECT 
    *,
    EXTRACT(EPOCH FROM (due_at - CURRENT_TIMESTAMP))/86400 as days_until_due
FROM course_assessments
WHERE 
    due_at IS NOT NULL 
    AND due_at > CURRENT_TIMESTAMP
ORDER BY due_at ASC;

CREATE VIEW overdue_assessments AS
SELECT 
    *,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - due_at))/86400 as days_overdue
FROM course_assessments
WHERE 
    due_at IS NOT NULL 
    AND due_at < CURRENT_TIMESTAMP
ORDER BY due_at DESC;
```
Click **Run** and verify success ✅

### Step 4: Verify Deployment

1. In the left sidebar, click **"Table Editor"**
2. You should see the `course_assessments` table listed
3. Click on it to view the table structure
4. You should see all 8 columns as defined

### Step 5: Test with Sample Data (Optional)

Run this query to insert test data:
```sql
INSERT INTO course_assessments (id, course_id, type, name, description, due_at)
VALUES (
    12345,
    213007,
    'assignment',
    'Final Project Report',
    'Submit your final project report including methodology, results, and conclusions.',
    '2024-12-15 23:59:00+00'
);
```

Then verify it was inserted:
```sql
SELECT * FROM course_assessments;
```

## 🔍 Testing Your Schema

### Test Queries to Run

**1. Get all assignments for a course:**
```sql
SELECT * FROM course_assessments 
WHERE course_id = 213007 AND type = 'assignment';
```

**2. Get upcoming assessments:**
```sql
SELECT * FROM upcoming_assessments 
WHERE days_until_due <= 7;
```

**3. Search by name:**
```sql
SELECT * FROM course_assessments 
WHERE name ILIKE '%project%';
```

## 🛡️ Security Settings (Optional)

### Row Level Security (RLS)
If you want to add basic security:

1. In Table Editor, click on your table
2. Click **"Settings"** 
3. Enable **"Row Level Security"**
4. Add policies as needed for your use case

### Basic Policy Example:
```sql
-- Allow all operations for authenticated users
CREATE POLICY "Allow all for authenticated users" 
ON course_assessments FOR ALL 
TO authenticated 
USING (true);
```

## 🎛️ Supabase Dashboard Features

After deployment, you can:

- **View Data**: Use Table Editor to browse records
- **Edit Data**: Add/modify records directly in the UI
- **API**: Access your data via auto-generated REST API
- **Real-time**: Enable real-time subscriptions if needed
- **Auth**: Add user authentication if required

## 📊 API Endpoints (Auto-generated)

Once deployed, Supabase automatically generates:

- **GET** `/rest/v1/course_assessments` - Get all assessments
- **POST** `/rest/v1/course_assessments` - Create new assessment
- **PATCH** `/rest/v1/course_assessments?id=eq.12345` - Update assessment
- **DELETE** `/rest/v1/course_assessments?id=eq.12345` - Delete assessment

## 🔧 Common Issues & Solutions

### Issue: "relation does not exist"
**Solution**: Make sure you're running queries in the correct order. Create table first, then indexes.

### Issue: Permission denied
**Solution**: Make sure you're logged in and have the right permissions on your Supabase project.

### Issue: Syntax errors
**Solution**: Copy the SQL exactly as provided, including semicolons and formatting.

## 📝 Next Steps

After successful deployment:

1. **Connect from Python**: Use the `supabase` Python client to connect
2. **Insert Real Data**: Use your Canvas scraper to populate the table
3. **Build Dashboard**: Use Supabase's built-in dashboard or build your own
4. **Add Notifications**: Set up email/SMS notifications for due dates

## 🔗 Useful Resources

- [Supabase SQL Editor Documentation](https://supabase.com/docs/guides/database/overview)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Supabase Python Client](https://github.com/supabase-community/supabase-py)

---

**✅ Your simplified assessments schema is now ready for Canvas data!**