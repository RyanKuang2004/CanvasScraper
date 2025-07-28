#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Canvas Client

Tests all functions in canvas_client.py with full coverage, following TDD principles
and backend development best practices for reliability, error handling, and edge cases.
"""

import pytest
import asyncio
import aiohttp
import json
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any, Optional
import sys
import os
from pathlib import Path

# Add parent directory to path to import canvas_client
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules under test
from src.canvas_client import (
    CanvasClient, 
    CanvasClientError, 
    CanvasAPIError
)

# Mock the config to avoid dependency issues
@pytest.fixture(autouse=True)
def mock_config():
    """Mock the Config class to provide test configuration"""
    with patch('src.canvas_client.Config') as mock_config_class:
        mock_config_class.CANVAS_URL = 'https://test.canvas.edu/api/v1'
        mock_config_class.CANVAS_API_TOKEN = 'test_token_123'
        yield mock_config_class


class TestCanvasClientExceptions:
    """Test custom exception classes"""
    
    def test_canvas_client_error_inheritance(self):
        """Test CanvasClientError is proper Exception subclass"""
        error = CanvasClientError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_canvas_api_error_attributes(self):
        """Test CanvasAPIError stores status code and endpoint"""
        error = CanvasAPIError("API Error", 500, "/test/endpoint")
        assert isinstance(error, CanvasClientError)
        assert error.status_code == 500
        assert error.endpoint == "/test/endpoint"
        assert str(error) == "API Error"


class TestCanvasClientInitialization:
    """Test CanvasClient constructor and configuration validation"""
    
    def test_init_with_valid_config(self, mock_config):
        """Test successful initialization with valid configuration"""
        client = CanvasClient()
        
        assert client.api_url == 'https://test.canvas.edu/api/v1'
        assert client.api_token == 'test_token_123'
        assert client.headers == {'Authorization': 'Bearer test_token_123'}
        assert client._session is None
        assert client._should_close_session is True
        assert isinstance(client.logger, logging.Logger)
    
    def test_init_with_provided_session(self, mock_config):
        """Test initialization with provided aiohttp session"""
        mock_session = Mock(spec=aiohttp.ClientSession)
        client = CanvasClient(session=mock_session)
        
        assert client._session is mock_session
        assert client._should_close_session is False
    
    def test_init_missing_api_url(self, mock_config):
        """Test initialization fails with missing API URL"""
        mock_config.CANVAS_URL = None
        
        with pytest.raises(CanvasClientError, match="Canvas API URL and token must be configured"):
            CanvasClient()
    
    def test_init_missing_api_token(self, mock_config):
        """Test initialization fails with missing API token"""
        mock_config.CANVAS_API_TOKEN = None
        
        with pytest.raises(CanvasClientError, match="Canvas API URL and token must be configured"):
            CanvasClient()
    
    def test_init_empty_api_url(self, mock_config):
        """Test initialization fails with empty API URL"""
        mock_config.CANVAS_URL = ""
        
        with pytest.raises(CanvasClientError, match="Canvas API URL and token must be configured"):
            CanvasClient()


class TestSessionManagement:
    """Test session context manager functionality"""
    
    @pytest.mark.asyncio
    async def test_get_session_with_provided_session(self, mock_config):
        """Test _get_session returns provided session"""
        mock_session = Mock(spec=aiohttp.ClientSession)
        client = CanvasClient(session=mock_session)
        
        async with client._get_session() as session:
            assert session is mock_session
    
    @pytest.mark.asyncio
    async def test_get_session_creates_new_session(self, mock_config):
        """Test _get_session creates new session when none provided"""
        client = CanvasClient()
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session_class.return_value.__aexit__.return_value = None
            
            async with client._get_session() as session:
                assert session is mock_session


class TestGetMethod:
    """Test the core _get method for API requests"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock aiohttp session for testing"""
        session = AsyncMock(spec=aiohttp.ClientSession)
        return session
    
    @pytest.fixture
    def client(self, mock_config):
        """Create CanvasClient instance for testing"""
        return CanvasClient()
    
    @pytest.mark.asyncio
    async def test_get_success_200(self, client, mock_session):
        """Test successful GET request returning JSON data"""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {'id': 123, 'name': 'Test Course'}
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get(mock_session, '/test/endpoint')
        
        assert result == {'id': 123, 'name': 'Test Course'}
        mock_session.get.assert_called_once_with(
            'https://test.canvas.edu/api/v1/test/endpoint',
            headers={'Authorization': 'Bearer test_token_123'}
        )
    
    @pytest.mark.asyncio
    async def test_get_not_found_404(self, client, mock_session):
        """Test GET request handling 404 Not Found"""
        mock_response = AsyncMock()
        mock_response.status = 404
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get(mock_session, '/test/endpoint')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_server_error_500(self, client, mock_session):
        """Test GET request handling server errors"""
        mock_response = AsyncMock()
        mock_response.status = 500
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with pytest.raises(CanvasAPIError) as exc_info:
            await client._get(mock_session, '/test/endpoint')
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.endpoint == '/test/endpoint'
        assert 'Failed to fetch /test/endpoint: 500' in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_client_error(self, client, mock_session):
        """Test GET request handling network errors"""
        mock_session.get.side_effect = aiohttp.ClientError("Connection failed")
        
        with pytest.raises(CanvasAPIError) as exc_info:
            await client._get(mock_session, '/test/endpoint')
        
        assert exc_info.value.status_code == 0
        assert exc_info.value.endpoint == '/test/endpoint'
        assert 'Network error fetching /test/endpoint' in str(exc_info.value)


class TestGetPaginatedMethod:
    """Test paginated API request handling"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_paginated_single_page(self, client, mock_session):
        """Test paginated request with single page of results"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = [{'id': 1}, {'id': 2}]
        
        # Create a proper mock headers object
        mock_headers = Mock()
        mock_headers.get.return_value = None  # No Link header
        mock_response.headers = mock_headers
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get_paginated(mock_session, '/test/endpoint')
        
        assert result == [{'id': 1}, {'id': 2}]
        mock_session.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_paginated_multiple_pages(self, client, mock_session):
        """Test paginated request with multiple pages"""
        # First page response
        mock_response1 = AsyncMock()
        mock_response1.status = 200
        mock_response1.json.return_value = [{'id': 1}, {'id': 2}]
        mock_headers1 = Mock()
        mock_headers1.get.return_value = '<https://test.canvas.edu/api/v1/test/endpoint?page=2>; rel="next"'
        mock_response1.headers = mock_headers1
        
        # Second page response
        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.json.return_value = [{'id': 3}, {'id': 4}]
        mock_headers2 = Mock()
        mock_headers2.get.return_value = None  # No more pages
        mock_response2.headers = mock_headers2
        
        # Mock session to return different responses for each call
        mock_session.get.return_value.__aenter__.side_effect = [mock_response1, mock_response2]
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get_paginated(mock_session, '/test/endpoint')
        
        assert result == [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}]
        assert mock_session.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_paginated_non_list_response(self, client, mock_session):
        """Test paginated request handling non-list response"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {'error': 'Invalid request'}  # Non-list response
        mock_response.headers.get.return_value = None
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get_paginated(mock_session, '/test/endpoint')
        
        assert result == {'error': 'Invalid request'}
    
    @pytest.mark.asyncio
    async def test_get_paginated_api_error(self, client, mock_session):
        """Test paginated request handling API errors"""
        mock_response = AsyncMock()
        mock_response.status = 403
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with pytest.raises(CanvasAPIError) as exc_info:
            await client._get_paginated(mock_session, '/test/endpoint')
        
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_get_paginated_network_error(self, client, mock_session):
        """Test paginated request handling network errors"""
        mock_session.get.side_effect = aiohttp.ClientError("Network timeout")
        
        with pytest.raises(CanvasAPIError) as exc_info:
            await client._get_paginated(mock_session, '/test/endpoint')
        
        assert exc_info.value.status_code == 0
        assert 'Network error' in str(exc_info.value)


class TestGetActiveCourses:
    """Test get_active_courses method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.mark.asyncio
    async def test_get_active_courses_success(self, client):
        """Test successful retrieval of active courses"""
        mock_courses = [
            {'id': 123, 'name': 'Course 1', 'workflow_state': 'available'},
            {'id': 456, 'name': 'Course 2', 'workflow_state': 'available'}
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_courses) as mock_paginated:
            result = await client.get_active_courses()
            
            expected = [
                {'id': 123, 'name': 'Course 1'},
                {'id': 456, 'name': 'Course 2'}
            ]
            assert result == expected
            mock_paginated.assert_called_once()
            # Check that the call includes the enrollment_state parameter
            call_args = mock_paginated.call_args[0]
            assert '/courses?enrollment_state=active' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_get_active_courses_empty(self, client):
        """Test get_active_courses with no courses"""
        with patch.object(client, '_get_paginated', return_value=[]):
            result = await client.get_active_courses()
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_active_courses_none_response(self, client):
        """Test get_active_courses with None response"""
        with patch.object(client, '_get_paginated', return_value=None):
            result = await client.get_active_courses()
            assert result == []


class TestGetModules:
    """Test get_modules method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_modules_success(self, client, mock_session):
        """Test successful module retrieval"""
        mock_modules = [
            {'id': 789, 'name': 'Module 1'},
            {'id': 790, 'name': 'Module 2'}
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_modules) as mock_paginated:
            result = await client.get_modules(mock_session, 123)
            
            assert result == mock_modules
            mock_paginated.assert_called_once_with(mock_session, '/courses/123/modules')
    
    @pytest.mark.asyncio
    async def test_get_modules_empty(self, client, mock_session):
        """Test get_modules with no modules"""
        with patch.object(client, '_get_paginated', return_value=[]):
            result = await client.get_modules(mock_session, 123)
            assert result == []


class TestGetModuleItems:
    """Test get_module_items method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_module_items_success(self, client, mock_session):
        """Test successful module item retrieval"""
        mock_items = [
            {'id': 1001, 'title': 'Item 1', 'type': 'Page'},
            {'id': 1002, 'title': 'Item 2', 'type': 'File'}
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_items) as mock_paginated:
            result = await client.get_module_items(mock_session, 123, 789)
            
            assert result == mock_items
            mock_paginated.assert_called_once_with(mock_session, '/courses/123/modules/789/items')


class TestGetPageContent:
    """Test get_page_content method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_page_content_success(self, client, mock_session):
        """Test successful page content retrieval"""
        mock_page_data = {'body': '<p>Page content here</p>'}
        
        with patch.object(client, '_get', return_value=mock_page_data) as mock_get:
            result = await client.get_page_content(mock_session, 123, 'test-page')
            
            assert result == '<p>Page content here</p>'
            mock_get.assert_called_once_with(mock_session, '/courses/123/pages/test-page')
    
    @pytest.mark.asyncio
    async def test_get_page_content_not_found(self, client, mock_session):
        """Test page content retrieval when page not found"""
        with patch.object(client, '_get', return_value=None):
            result = await client.get_page_content(mock_session, 123, 'nonexistent-page')
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_page_content_no_body(self, client, mock_session):
        """Test page content retrieval when page has no body"""
        mock_page_data = {'title': 'Test Page'}  # No body field
        
        with patch.object(client, '_get', return_value=mock_page_data):
            result = await client.get_page_content(mock_session, 123, 'test-page')
            assert result is None


class TestGetQuizContent:
    """Test get_quiz_content method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_quiz_content_success(self, client, mock_session):
        """Test successful quiz content retrieval"""
        mock_quiz_data = {'description': '<p>Quiz instructions</p>'}
        
        with patch.object(client, '_get', return_value=mock_quiz_data) as mock_get:
            result = await client.get_quiz_content(mock_session, 123, 456)
            
            assert result == '<p>Quiz instructions</p>'
            mock_get.assert_called_once_with(mock_session, '/courses/123/quizzes/456')
    
    @pytest.mark.asyncio
    async def test_get_quiz_content_not_found(self, client, mock_session):
        """Test quiz content retrieval when quiz not found"""
        with patch.object(client, '_get', return_value=None):
            result = await client.get_quiz_content(mock_session, 123, 456)
            assert result is None


class TestGetFileContent:
    """Test get_file_content method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_file_content_text_file(self, client, mock_session):
        """Test file content retrieval for text files"""
        mock_file_info = {
            'url': 'https://files.canvas.edu/download/123',
            'content-type': 'text/plain',
            'display_name': 'test.txt'
        }
        
        mock_file_response = AsyncMock()
        mock_file_response.status = 200
        mock_file_response.text.return_value = 'File content here'
        
        with patch.object(client, '_get', return_value=mock_file_info):
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            mock_session.get.return_value.__aexit__.return_value = None
            
            result = await client.get_file_content(mock_session, 123)
            
            assert result == 'File content here'
    
    @pytest.mark.asyncio
    async def test_get_file_content_binary_file(self, client, mock_session):
        """Test file content retrieval for binary files"""
        mock_file_info = {
            'url': 'https://files.canvas.edu/download/123',
            'content-type': 'application/pdf',
            'display_name': 'document.pdf'
        }
        
        mock_file_response = AsyncMock()
        mock_file_response.status = 200
        mock_file_response.read.return_value = b'PDF content here'  # 16 bytes
        
        with patch.object(client, '_get', return_value=mock_file_info):
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            mock_session.get.return_value.__aexit__.return_value = None
            
            result = await client.get_file_content(mock_session, 123)
            
            assert result == 'Binary file: document.pdf (application/pdf, 16 bytes)'
    
    @pytest.mark.asyncio
    async def test_get_file_content_unicode_error(self, client, mock_session):
        """Test file content retrieval with encoding errors"""
        mock_file_info = {
            'url': 'https://files.canvas.edu/download/123',
            'content-type': 'text/plain',
            'display_name': 'bad_encoding.txt'
        }
        
        mock_file_response = AsyncMock()
        mock_file_response.status = 200
        mock_file_response.text.side_effect = UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte')
        
        with patch.object(client, '_get', return_value=mock_file_info):
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            mock_session.get.return_value.__aexit__.return_value = None
            
            result = await client.get_file_content(mock_session, 123)
            
            assert result == 'File with encoding issues: bad_encoding.txt'
    
    @pytest.mark.asyncio
    async def test_get_file_content_no_file_info(self, client, mock_session):
        """Test file content retrieval when file info not found"""
        with patch.object(client, '_get', return_value=None):
            result = await client.get_file_content(mock_session, 123)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_file_content_no_download_url(self, client, mock_session):
        """Test file content retrieval when file has no download URL"""
        mock_file_info = {'display_name': 'test.txt'}  # No URL
        
        with patch.object(client, '_get', return_value=mock_file_info):
            result = await client.get_file_content(mock_session, 123)
            assert result is None


class TestFetchModuleItemContent:
    """Test fetch_module_item_content method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_fetch_module_item_content_page(self, client, mock_session):
        """Test fetching content for Page module item"""
        module_item = {
            'type': 'Page',
            'page_url': 'test-page-slug'
        }
        
        with patch.object(client, 'get_page_content', return_value='Page content') as mock_get_page:
            result = await client.fetch_module_item_content(mock_session, 123, module_item)
            
            assert result == 'Page content'
            mock_get_page.assert_called_once_with(mock_session, 123, 'test-page-slug')
    
    @pytest.mark.asyncio
    async def test_fetch_module_item_content_file(self, client, mock_session):
        """Test fetching content for File module item"""
        module_item = {
            'type': 'File',
            'content_id': 456
        }
        
        with patch.object(client, 'get_file_content', return_value='File content') as mock_get_file:
            result = await client.fetch_module_item_content(mock_session, 123, module_item)
            
            assert result == 'File content'
            mock_get_file.assert_called_once_with(mock_session, 456)
    
    @pytest.mark.asyncio
    async def test_fetch_module_item_content_unsupported_type(self, client, mock_session):
        """Test fetching content for unsupported module item type"""
        module_item = {
            'type': 'Assignment',  # Not supported by this method
            'content_id': 789
        }
        
        result = await client.fetch_module_item_content(mock_session, 123, module_item)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_module_item_content_missing_data(self, client, mock_session):
        """Test fetching content when required data is missing"""
        module_item = {
            'type': 'Page'
            # Missing page_url
        }
        
        result = await client.fetch_module_item_content(mock_session, 123, module_item)
        assert result is None


class TestHtmlToText:
    """Test _html_to_text utility method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    def test_html_to_text_basic_html(self, client):
        """Test HTML to text conversion with basic HTML"""
        html = '<p>This is <strong>bold</strong> and <em>italic</em> text.</p>'
        result = client._html_to_text(html)
        assert result == 'This is bold and italic text.'
    
    def test_html_to_text_complex_html(self, client):
        """Test HTML to text conversion with complex HTML"""
        html = '''
        <div>
            <h1>Title</h1>
            <p>Paragraph with <a href="#">link</a>.</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
        </div>
        '''
        result = client._html_to_text(html)
        expected = 'Title Paragraph with link . Item 1 Item 2'
        assert result == expected
    
    def test_html_to_text_none_input(self, client):
        """Test HTML to text conversion with None input"""
        result = client._html_to_text(None)
        assert result == ""
    
    def test_html_to_text_empty_string(self, client):
        """Test HTML to text conversion with empty string"""
        result = client._html_to_text("")
        assert result == ""
    
    def test_html_to_text_whitespace_normalization(self, client):
        """Test HTML to text conversion normalizes whitespace"""
        html = '<p>Text   with    multiple    spaces</p>'
        result = client._html_to_text(html)
        assert result == 'Text with multiple spaces'
    
    def test_html_to_text_beautifulsoup_not_available(self, client):
        """Test HTML to text conversion when BeautifulSoup not available"""
        html = '<p>Test content</p>'
        
        # Mock the import of BeautifulSoup to raise ImportError
        with patch('builtins.__import__', side_effect=ImportError) as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'bs4':
                    raise ImportError("No module named 'bs4'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            result = client._html_to_text(html)
            assert result == html  # Returns raw HTML as fallback
    
    def test_html_to_text_parsing_error(self, client):
        """Test HTML to text conversion with parsing errors"""
        html = '<p>Test content</p>'
        
        # Mock BeautifulSoup constructor to raise an exception
        with patch('bs4.BeautifulSoup', side_effect=Exception("Parsing error")):
            result = client._html_to_text(html)
            assert result == html  # Returns raw HTML as fallback


class TestGetAssignments:
    """Test get_assignments method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_assignments_success(self, client, mock_session):
        """Test successful assignment retrieval"""
        mock_assignments = [
            {
                'id': 123,
                'name': 'Assignment 1',
                'due_at': '2024-12-31T23:59:59Z',
                'description': '<p>Assignment <strong>description</strong></p>'
            },
            {
                'id': 124,
                'name': 'Assignment 2',
                'due_at': None,
                'description': None
            }
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_assignments) as mock_paginated:
            with patch.object(client, '_html_to_text', side_effect=lambda x: 'Assignment description' if x else '') as mock_html:
                result = await client.get_assignments(mock_session, 123)
                
                expected = [
                    {
                        'name': 'Assignment 1',
                        'due_at': '2024-12-31T23:59:59Z',
                        'type': 'assignment',
                        'description': 'Assignment description'
                    },
                    {
                        'name': 'Assignment 2',
                        'due_at': None,
                        'type': 'assignment',
                        'description': ''
                    }
                ]
                
                assert result == expected
                mock_paginated.assert_called_once_with(mock_session, '/courses/123/assignments')
    
    @pytest.mark.asyncio
    async def test_get_assignments_empty(self, client, mock_session):
        """Test get_assignments with no assignments"""
        with patch.object(client, '_get_paginated', return_value=[]):
            result = await client.get_assignments(mock_session, 123)
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_assignments_none_response(self, client, mock_session):
        """Test get_assignments with None response"""
        with patch.object(client, '_get_paginated', return_value=None):
            result = await client.get_assignments(mock_session, 123)
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_assignments_missing_name(self, client, mock_session):
        """Test get_assignments with assignment missing name"""
        mock_assignments = [
            {
                'id': 123,
                # Missing 'name' field
                'due_at': '2024-12-31T23:59:59Z',
                'description': 'Test description'
            }
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_assignments):
            with patch.object(client, '_html_to_text', return_value='Test description'):
                result = await client.get_assignments(mock_session, 123)
                
                assert len(result) == 1
                assert result[0]['name'] == 'Unnamed Assignment'  # Default name
    
    @pytest.mark.asyncio
    async def test_get_assignments_canvas_api_error(self, client, mock_session):
        """Test get_assignments handling Canvas API errors"""
        with patch.object(client, '_get_paginated', side_effect=CanvasAPIError("API Error", 500, "/assignments")):
            with pytest.raises(CanvasAPIError):
                await client.get_assignments(mock_session, 123)
    
    @pytest.mark.asyncio
    async def test_get_assignments_unexpected_error(self, client, mock_session):
        """Test get_assignments handling unexpected errors"""
        with patch.object(client, '_get_paginated', side_effect=Exception("Unexpected error")):
            with pytest.raises(Exception, match="Unexpected error"):
                await client.get_assignments(mock_session, 123)


class TestGetQuizzes:
    """Test get_quizzes method"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=aiohttp.ClientSession)
    
    @pytest.mark.asyncio
    async def test_get_quizzes_success(self, client, mock_session):
        """Test successful quiz retrieval"""
        mock_quizzes = [
            {
                'id': 456,
                'title': 'Quiz 1',
                'due_at': '2024-12-31T23:59:59Z',
                'description': '<p>Quiz <em>instructions</em></p>'
            },
            {
                'id': 457,
                'title': 'Quiz 2',
                'due_at': None,
                'description': ''
            }
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_quizzes) as mock_paginated:
            with patch.object(client, '_html_to_text', side_effect=lambda x: 'Quiz instructions' if x else '') as mock_html:
                result = await client.get_quizzes(mock_session, 123)
                
                expected = [
                    {
                        'name': 'Quiz 1',
                        'due_at': '2024-12-31T23:59:59Z',
                        'type': 'quiz',
                        'description': 'Quiz instructions'
                    },
                    {
                        'name': 'Quiz 2',
                        'due_at': None,
                        'type': 'quiz',
                        'description': ''
                    }
                ]
                
                assert result == expected
                mock_paginated.assert_called_once_with(mock_session, '/courses/123/quizzes')
    
    @pytest.mark.asyncio
    async def test_get_quizzes_empty(self, client, mock_session):
        """Test get_quizzes with no quizzes"""
        with patch.object(client, '_get_paginated', return_value=[]):
            result = await client.get_quizzes(mock_session, 123)
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_quizzes_missing_title(self, client, mock_session):
        """Test get_quizzes with quiz missing title"""
        mock_quizzes = [
            {
                'id': 456,
                # Missing 'title' field
                'due_at': '2024-12-31T23:59:59Z',
                'description': 'Test description'
            }
        ]
        
        with patch.object(client, '_get_paginated', return_value=mock_quizzes):
            with patch.object(client, '_html_to_text', return_value='Test description'):
                result = await client.get_quizzes(mock_session, 123)
                
                assert len(result) == 1
                assert result[0]['name'] == 'Unnamed Quiz'  # Default name
    
    @pytest.mark.asyncio
    async def test_get_quizzes_canvas_api_error(self, client, mock_session):
        """Test get_quizzes handling Canvas API errors"""
        with patch.object(client, '_get_paginated', side_effect=CanvasAPIError("API Error", 404, "/quizzes")):
            with pytest.raises(CanvasAPIError):
                await client.get_quizzes(mock_session, 123)


class TestIntegrationScenarios:
    """Integration tests for realistic usage scenarios"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.mark.asyncio
    async def test_full_course_content_retrieval(self, client):
        """Test complete workflow: courses -> modules -> items -> content"""
        # Mock the full chain of API calls
        mock_courses = [{'id': 123, 'name': 'Test Course'}]
        mock_modules = [{'id': 789, 'name': 'Test Module'}]
        mock_items = [
            {'id': 1001, 'title': 'Test Page', 'type': 'Page', 'page_url': 'test-page'},
            {'id': 1002, 'title': 'Test File', 'type': 'File', 'content_id': 456}
        ]
        
        with patch.object(client, '_get_paginated') as mock_paginated:
            with patch.object(client, 'get_page_content', return_value='Page content') as mock_page:
                with patch.object(client, 'get_file_content', return_value='File content') as mock_file:
                    
                    # Mock session
                    mock_session = AsyncMock(spec=aiohttp.ClientSession)
                    
                    # Test course retrieval
                    mock_paginated.return_value = mock_courses
                    courses = await client.get_active_courses()
                    assert len(courses) == 1
                    
                    # Test module retrieval
                    mock_paginated.return_value = mock_modules
                    modules = await client.get_modules(mock_session, 123)
                    assert len(modules) == 1
                    
                    # Test item retrieval
                    mock_paginated.return_value = mock_items
                    items = await client.get_module_items(mock_session, 123, 789)
                    assert len(items) == 2
                    
                    # Test content retrieval
                    page_content = await client.fetch_module_item_content(mock_session, 123, mock_items[0])
                    file_content = await client.fetch_module_item_content(mock_session, 123, mock_items[1])
                    
                    assert page_content == 'Page content'
                    assert file_content == 'File content'


class TestErrorHandlingScenarios:
    """Test comprehensive error handling scenarios"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_scenario(self, client):
        """Test handling of rate limiting (429 Too Many Requests)"""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        
        mock_response = AsyncMock()
        mock_response.status = 429
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with pytest.raises(CanvasAPIError) as exc_info:
            await client._get(mock_session, '/test/endpoint')
        
        assert exc_info.value.status_code == 429
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, client):
        """Test handling of authentication failures (401 Unauthorized)"""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        
        mock_response = AsyncMock()
        mock_response.status = 401
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with pytest.raises(CanvasAPIError) as exc_info:
            await client._get(mock_session, '/test/endpoint')
        
        assert exc_info.value.status_code == 401


class TestPerformanceAndEdgeCases:
    """Test performance considerations and edge cases"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.mark.asyncio
    async def test_large_paginated_response(self, client):
        """Test handling of large paginated responses"""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        
        # Simulate 5 pages of 100 items each
        pages = []
        for page in range(5):
            page_data = [{'id': i + (page * 100), 'name': f'Item {i + (page * 100)}'} for i in range(100)]
            pages.append(page_data)
        
        responses = []
        for i, page_data in enumerate(pages):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = page_data
            
            # Create a proper Mock for headers instead of AsyncMock
            mock_headers = Mock()
            if i < len(pages) - 1:  # Not the last page
                mock_headers.get.return_value = f'<https://test.canvas.edu/api/v1/test?page={i+2}>; rel="next"'
            else:  # Last page
                mock_headers.get.return_value = None
            mock_response.headers = mock_headers
            
            responses.append(mock_response)
        
        mock_session.get.return_value.__aenter__.side_effect = responses
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get_paginated(mock_session, '/test')
        
        assert len(result) == 500  # 5 pages * 100 items
        assert result[0]['id'] == 0
        assert result[-1]['id'] == 499
    
    @pytest.mark.asyncio
    async def test_malformed_link_header_parsing(self, client):
        """Test parsing of malformed Link headers in pagination"""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        
        # Test with malformed Link header
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = [{'id': 1}]
        
        # Create proper Mock for headers
        mock_headers = Mock()
        mock_headers.get.return_value = 'malformed-link-header'
        mock_response.headers = mock_headers
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        # This should not raise an exception, just stop pagination gracefully
        result = await client._get_paginated(mock_session, '/test')
        assert len(result) == 1


class TestAdditionalCoverageScenarios:
    """Additional tests to improve coverage"""
    
    @pytest.fixture
    def client(self, mock_config):
        return CanvasClient()
    
    @pytest.mark.asyncio
    async def test_get_paginated_non_list_first_page(self, client):
        """Test _get_paginated when first page returns non-list"""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {'single_item': 'test'}  # Non-list response
        
        mock_headers = Mock()
        mock_headers.get.return_value = None
        mock_response.headers = mock_headers
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        result = await client._get_paginated(mock_session, '/test')
        assert result == {'single_item': 'test'}
    
    @pytest.mark.asyncio
    async def test_get_file_content_download_error(self, client):
        """Test get_file_content when file download fails"""
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        
        # Mock file info response
        mock_file_response = AsyncMock()
        mock_file_response.status = 200
        mock_file_response.json.return_value = {
            'url': 'https://example.com/file.pdf',
            'content-type': 'application/pdf',
            'display_name': 'test.pdf'
        }
        
        # Mock download response with error
        mock_download_response = AsyncMock()
        mock_download_response.status = 404
        
        # Setup side_effect for context manager behavior
        def get_side_effect(*args, **kwargs):
            if 'files' in args[0]:
                context_mock = AsyncMock()
                context_mock.__aenter__.return_value = mock_file_response
                context_mock.__aexit__.return_value = None
                return context_mock
            else:
                context_mock = AsyncMock()
                context_mock.__aenter__.return_value = mock_download_response
                context_mock.__aexit__.return_value = None
                return context_mock
        
        mock_session.get.side_effect = get_side_effect
        
        result = await client.get_file_content(mock_session, 123)
        assert result is None


if __name__ == '__main__':
    # Run tests with coverage
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--cov=src.canvas_client',
        '--cov-report=term-missing',
        '--cov-report=html:htmlcov',
        '--cov-fail-under=95'
    ])