# Enhanced Canvas Scraper Deployment Guide

Complete deployment guide for the enhanced Canvas scraper with file processing, chunking, deduplication, and Supabase integration.

## Features Implemented ✅

### Phase 1: Core Infrastructure
- ✅ **CourseManager**: Configuration-driven course selection via `config/courses.yml`
- ✅ **Content Fingerprinting**: SHA-256 hashing for deduplication
- ✅ **State Tracking**: Incremental processing and change detection
- ✅ **Melbourne Timezone Scheduling**: 12pm and 8pm automated runs

### Phase 2: File Processing & Storage
- ✅ **Multi-format File Processors**: PDF, PPTX, DOCX with advanced extraction
- ✅ **Intelligent Text Chunking**: Semantic-aware chunking with overlap and structure preservation
- ✅ **Content Deduplication**: Fingerprint-based detection of unchanged files
- ✅ **Supabase Integration**: Complete storage with full-text search and analytics
- ✅ **Docker Configuration**: Enhanced with OCR support and new dependencies

## Quick Start

### 1. Environment Setup

```bash
# Clone and navigate
git clone <repository>
cd CanvasScraper

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

```bash
# Canvas API (Required)
CANVAS_API_TOKEN=your_canvas_api_token
CANVAS_URL=https://canvas.lms.unimelb.edu.au/api/v1

# Supabase (Required for persistence)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key  # For admin operations
```

### 3. Configure Courses

Edit `config/courses.yml`:

```yaml
# Course selection configuration
enabled_courses:
  - "12345"  # Course ID from Canvas
  - "67890"

# Scraping preferences
scraping_preferences:
  file_types:
    - pdf
    - pptx
    - docx
  max_file_size_mb: 50
  skip_hidden_modules: true
  
# Scheduling (Melbourne timezone)
scheduling:
  enabled: true
  times:
    - "12:00"  # 12pm
    - "20:00"  # 8pm
```

### 4. Setup Supabase Database

```bash
# Run the schema setup in Supabase SQL Editor
cat database/supabase_schema.sql | supabase db reset
# OR copy/paste the contents into Supabase dashboard
```

### 5. Run the Enhanced Scraper

```bash
# One-time sync
python scripts/run_enhanced_scraper.py run

# Force reprocess all files
python scripts/run_enhanced_scraper.py run --force

# Run as daemon with scheduling
python scripts/run_enhanced_scraper.py daemon

# Search content
python scripts/run_enhanced_scraper.py search --query "machine learning"

# View statistics
python scripts/run_enhanced_scraper.py stats
```

## Docker Deployment

### Build and Run

```bash
# Build enhanced image
docker build -t canvas-scraper-enhanced .

# Run with environment file
docker run -d \
  --name canvas-scraper \
  --env-file .env \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/downloads:/app/downloads \
  canvas-scraper-enhanced

# View logs
docker logs -f canvas-scraper
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  canvas-scraper:
    build: .
    environment:
      - CANVAS_API_TOKEN=${CANVAS_API_TOKEN}
      - CANVAS_URL=${CANVAS_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
    volumes:
      - ./config:/app/config:ro
      - ./downloads:/app/downloads
      - ./logs:/app/logs
    restart: unless-stopped
```

```bash
# Run with compose
docker-compose up -d
```

## Architecture Overview

### Component Structure

```
src/
├── canvas_orchestrator.py      # Main coordination logic
├── course_manager.py           # Course selection and configuration
├── file_processor_manager.py   # File processing coordination
├── content_fingerprint.py      # Content deduplication
├── state_manager.py           # Processing state tracking
├── text_chunker.py            # Intelligent text chunking
├── scheduler.py               # Melbourne timezone scheduling
├── supabase_client.py         # Database integration
└── file_processors/           # Format-specific processors
    ├── base_processor.py
    ├── pdf_processor.py       # PDF extraction with OCR fallback
    ├── pptx_processor.py      # PowerPoint slide processing
    └── docx_processor.py      # Word document processing
```

### Data Flow

1. **Course Configuration** → CourseManager loads enabled courses
2. **Content Discovery** → Canvas API fetches modules and files
3. **Deduplication Check** → Content fingerprints prevent reprocessing
4. **File Processing** → Multi-format text extraction with metadata
5. **Text Chunking** → Semantic-aware chunks with overlap
6. **Storage** → Supabase database with full-text search
7. **Scheduling** → Automated runs at configured times

## Supabase Integration

### Database Schema

The enhanced scraper uses 8 main tables:

- **courses**: Canvas course information
- **modules**: Course module metadata
- **file_contents**: File processing metadata
- **content_texts**: Full extracted text content
- **content_chunks**: Chunked text for retrieval
- **processing_state**: Deduplication and state tracking
- **content_embeddings**: Vector embeddings (future)
- **search_analytics**: Search query tracking

### Features Available

```bash
# Full-text search across all content
SELECT * FROM search_content('machine learning', 'course_12345', 20);

# Course content summary
SELECT * FROM get_course_content_summary('course_12345');

# Real-time dashboard access via Supabase UI
```

## Advanced Features

### 1. Content Deduplication

The system uses SHA-256 content fingerprints to avoid reprocessing:

- **File-level**: Skip unchanged files completely
- **Content-level**: Detect text changes within files
- **Chunk-level**: Track individual chunk modifications

### 2. Intelligent Text Chunking

```python
# Chunking preserves document structure
chunks = SmartChunker(
    chunk_size=1000,        # Target chunk size
    overlap=200,            # Overlap between chunks
    preserve_structure=True # Maintain headings/sections
).chunk_text(text, file_id, metadata)
```

### 3. Multi-Format Processing

- **PDF**: pdfplumber → PyPDF2 → OCR (Tesseract) fallback chain
- **PPTX**: Slide content + speaker notes extraction
- **DOCX**: Paragraph and formatting preservation
- **Metadata**: Author, title, creation date, keywords

### 4. Search Capabilities

```bash
# Search with course filtering
python scripts/run_enhanced_scraper.py search \
  --query "neural networks" \
  --course-id "12345"

# Results include context and source information
```

## Monitoring and Maintenance

### Statistics Dashboard

```bash
# Overall statistics
python scripts/run_enhanced_scraper.py stats

# Course-specific statistics
python scripts/run_enhanced_scraper.py stats --course-id "12345"
```

### Log Management

```bash
# View processing logs
tail -f logs/canvas_scraper.log

# Docker logs
docker logs -f canvas-scraper
```

### Database Maintenance

```sql
-- Clean up old content (90+ days)
SELECT cleanup_old_content(90);

-- View processing status
SELECT * FROM processing_status;

-- Search analytics
SELECT query, COUNT(*) as frequency 
FROM search_analytics 
GROUP BY query 
ORDER BY frequency DESC;
```

## Performance Optimization

### Recommended Settings

```yaml
# config/courses.yml - Performance tuning
scraping_preferences:
  max_file_size_mb: 50      # Limit large files
  concurrent_downloads: 5    # Parallel processing
  chunk_size: 1000          # Optimal for embedding
  chunk_overlap: 200        # Good for retrieval
```

### Hardware Requirements

- **CPU**: 2+ cores (for parallel processing)
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 10GB+ for file downloads and processing
- **Network**: Stable connection to Canvas and Supabase

## Troubleshooting

### Common Issues

1. **Supabase Connection**
   ```bash
   # Check credentials
   echo $SUPABASE_URL
   echo $SUPABASE_ANON_KEY
   ```

2. **Canvas API Rate Limits**
   ```bash
   # Check API token permissions
   curl -H "Authorization: Bearer $CANVAS_API_TOKEN" \
        "$CANVAS_URL/users/self"
   ```

3. **OCR Dependencies**
   ```bash
   # Install Tesseract (Ubuntu/Debian)
   sudo apt-get install tesseract-ocr tesseract-ocr-eng
   ```

4. **Python Dependencies**
   ```bash
   # Reinstall with latest versions
   pip install -r requirements.txt --upgrade
   ```

### Support

The enhanced Canvas scraper is a production-ready system with comprehensive error handling, logging, and monitoring capabilities. All components have been tested and integrated successfully.

For additional support:
1. Check the detailed logs in `/app/logs/`
2. Review the Supabase dashboard for data insights
3. Use the built-in statistics and search commands
4. Monitor Docker container health and resource usage