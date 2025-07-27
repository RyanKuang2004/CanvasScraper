# Canvas Scraper Enhanced

A production-ready Canvas LMS content extraction and management system with clean architecture and minimal dependencies.

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone and enter project
git clone <repository-url>
cd CanvasScraper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Canvas API

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your Canvas API token
CANVAS_API_TOKEN=your_canvas_api_token_here
CANVAS_URL=https://canvas.lms.unimelb.edu.au/api/v1
```

### 3. Run the Scraper

```bash
# Basic execution
python3 scripts/run_scraper.py

# Or run directly
python3 -m src.canvas_client
```

## 📁 Project Structure

```
canvas-scraper/
├── src/                          # Core source code
│   ├── canvas_client.py          # Main Canvas API client
│   ├── config.py                 # Configuration management
│   └── __init__.py
├── scripts/                      # Deployment and utility scripts
│   ├── run_scraper.py           # Simple runner with logging
│   ├── setup_cron.sh            # Automated scheduling
│   ├── setup_supabase.py        # Optional Supabase integration
│   └── test_supabase_setup.py   # Supabase testing
├── database/                     # Database schemas (optional)
│   ├── schema.sql               # PostgreSQL schema
│   └── supabase_quick_setup.sql # Supabase setup
├── tests/                        # Test suite
│   ├── test_canvas_client.py    # Core functionality tests
│   ├── conftest.py              # Test configuration
│   └── __init__.py
├── logs/                         # Application logs (auto-created)
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
├── CLAUDE.md                     # AI assistant guidance
└── README.md                     # This file
```

## ⚙️ Deployment Options

### Option 1: Scheduled Execution (Recommended)

```bash
# Set up daily automated runs at 2 AM
chmod +x scripts/setup_cron.sh
./scripts/setup_cron.sh

# View cron jobs
crontab -l

# Check logs
tail -f logs/cron.log
```

### Option 2: Manual Execution

```bash
# Run once with logging
python3 scripts/run_scraper.py

# View logs
ls logs/
```

### Option 3: Enhanced Features (Optional)

```bash
# Set up Supabase integration for database storage
python3 scripts/setup_supabase.py

# Test Supabase connection
python3 scripts/test_supabase_setup.py
```

## 🔧 Configuration

### Required Environment Variables

- `CANVAS_API_TOKEN`: Your Canvas API access token
- `CANVAS_URL`: Canvas API base URL (default: University of Melbourne)

### Optional Environment Variables

- `SUPABASE_URL`: Supabase project URL (for enhanced features)
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_KEY`: Supabase service key
- `LOG_LEVEL`: Logging level (default: INFO)

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_canvas_client.py

# Run with coverage
pytest --cov=src tests/
```

## 📊 Features

### ✅ Current Features
- **Canvas API Integration**: Secure bearer token authentication
- **Multi-Content Support**: PDFs, HTML pages, quizzes, assignments
- **Async Processing**: Concurrent API requests for performance
- **Error Handling**: Graceful handling of missing resources
- **Logging**: Comprehensive logging with file rotation
- **Clean Architecture**: Organized codebase with separation of concerns

### 🔄 Optional Enhancements
- **Database Storage**: PostgreSQL/Supabase integration
- **Text Extraction**: Multi-format content processing
- **Full-Text Search**: Content indexing and search capabilities
- **Real-Time Dashboard**: Supabase-powered data visualization

## 🛡️ Security

- Environment-based configuration (no hardcoded credentials)
- Bearer token authentication for Canvas API
- Secure credential management with .env files
- Input validation and error handling

## 📈 Performance

- **Async/Await**: Non-blocking I/O for API requests
- **Minimal Dependencies**: Lean package footprint
- **Efficient Logging**: Structured logging with rotation
- **Clean Code**: Maintainable and readable codebase

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and test: `pytest tests/`
4. Commit changes: `git commit -m "Add feature"`
5. Push to branch: `git push origin feature-name`
6. Create a Pull Request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the logs in `logs/` directory
2. Review environment configuration in `.env`
3. Run tests to verify functionality: `pytest tests/`
4. Create an issue in the repository

---

**Status**: ✅ Production Ready | **Architecture**: Clean & Minimal | **Dependencies**: 12 core packages