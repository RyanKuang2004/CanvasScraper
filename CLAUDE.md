# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This is a Python project using Canvas LMS API integration. Common commands:

```bash
# Run the main scraper
python canvas_client.py

# Run tests
pytest tests/

# Run specific test file
pytest tests/test_canvas_client.py

# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt

# Install core dependencies manually
pip install aiohttp python-dotenv

# Install testing dependencies
pip install pytest pytest-asyncio
```

## Architecture Overview

This is a Canvas LMS scraper that retrieves PDFs/PPTX from courses and converts them to text.

### Core Components

- **`config.py`**: Configuration management using environment variables
  - Uses `python-dotenv` to load `.env` file
  - Configures Canvas API URL (University of Melbourne) and API token

- **`canvas_client.py`**: Main Canvas API client implementation
  - `CanvasClient` class handles all Canvas API interactions
  - Async HTTP requests using `aiohttp`
  - Supports fetching courses, modules, items, pages, quizzes, files, and due dates
  - Main execution flow demonstrates full course data retrieval

### Key Features

- Asynchronous API calls for performance
- Handles various Canvas content types (Pages, Files, Quizzes)
- Filters for active course enrollments only
- Due date tracking for assignments and quizzes
- Error handling for 404s and other HTTP errors

### Environment Setup

Requires `.env` file with:
```
CANVAS_API_TOKEN=your_canvas_api_token
```

### Data Flow

1. Authenticate with Canvas API using bearer token
2. Fetch active courses for authenticated user
3. For each course, retrieve modules and their items
4. Extract content from pages, files, and other resources
5. Track upcoming assignments and quiz due dates

- **`tests/`**: Test suite for the Canvas client
  - `test_canvas_client.py`: Comprehensive tests for all CanvasClient methods
  - `conftest.py`: Shared test fixtures and configuration
  - Uses `pytest` and `pytest-asyncio` for async testing

The codebase is structured as a simple Python application focused on Canvas LMS data extraction and processing.