import pytest
import asyncio
import aiohttp
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date
import sys
import os

# Add parent directory to path to import canvas_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.canvas_client import CanvasClient
from src.config import Config


class TestCanvasClient:
    """Test suite for CanvasClient class."""

    @pytest.fixture
    def client(self):
        """Create a CanvasClient instance for testing."""
        return CanvasClient()

    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session."""
        session = Mock()
        return session

    @pytest.mark.asyncio
    async def test_get_request_success(self, client, mock_session):
        """Test successful GET request."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"test": "data"})
        
        # Create a proper async context manager mock
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        result = await client._get(mock_session, "/test-endpoint")
        
        assert result == {"test": "data"}
        mock_session.get.assert_called_once_with(
            f"{Config.CANVAS_URL}/test-endpoint",
            headers={'Authorization': f'Bearer {Config.CANVAS_API_TOKEN}'}
        )

    @pytest.mark.asyncio
    async def test_get_request_404(self, client, mock_session):
        """Test GET request returning 404."""
        mock_response = Mock()
        mock_response.status = 404
        
        # Create a proper async context manager mock
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        result = await client._get(mock_session, "/nonexistent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_request_error(self, client, mock_session):
        """Test GET request returning error status."""
        mock_response = Mock()
        mock_response.status = 500
        
        # Create a proper async context manager mock
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        with pytest.raises(Exception, match="Failed to fetch /error: 500"):
            await client._get(mock_session, "/error")

    @pytest.mark.asyncio
    async def test_get_active_courses(self, client):
        """Test retrieving active courses."""
        mock_courses = [
            {
                "id": 1,
                "name": "Course 1",
                "enrollments": [{"enrollment_state": "active"}]
            },
            {
                "id": 2,
                "name": "Course 2",
                "enrollments": [{"enrollment_state": "inactive"}]
            },
            {
                "id": 3,
                "name": "Course 3",
                "enrollments": [{"enrollment_state": "active"}]
            }
        ]

        with patch.object(client, '_get', return_value=mock_courses):
            result = await client.get_active_courses()
            
            expected = [
                {"id": 1, "name": "Course 1"},
                {"id": 3, "name": "Course 3"}
            ]
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_modules(self, client, mock_session):
        """Test retrieving modules for a course."""
        mock_modules = [
            {"id": 1, "name": "Module 1"},
            {"id": 2, "name": "Module 2"}
        ]

        with patch.object(client, '_get', return_value=mock_modules):
            result = await client.get_modules(mock_session, 123)
            
            assert result == mock_modules
            client._get.assert_called_once_with(mock_session, "/courses/123/modules")

    @pytest.mark.asyncio
    async def test_get_module_items(self, client, mock_session):
        """Test retrieving items within a module."""
        mock_items = [
            {"id": 1, "title": "Item 1", "type": "Page"},
            {"id": 2, "title": "Item 2", "type": "File"}
        ]

        with patch.object(client, '_get', return_value=mock_items):
            result = await client.get_module_items(mock_session, 123, 456)
            
            assert result == mock_items
            client._get.assert_called_once_with(mock_session, "/courses/123/modules/456/items")

    @pytest.mark.asyncio
    async def test_get_page_content(self, client, mock_session):
        """Test retrieving page content."""
        mock_page = {"body": "<p>Page content here</p>"}

        with patch.object(client, '_get', return_value=mock_page):
            result = await client.get_page_content(mock_session, 123, "test-page")
            
            assert result == "<p>Page content here</p>"
            client._get.assert_called_once_with(mock_session, "/courses/123/pages/test-page")

    @pytest.mark.asyncio
    async def test_get_page_content_none(self, client, mock_session):
        """Test retrieving page content when page doesn't exist."""
        with patch.object(client, '_get', return_value=None):
            result = await client.get_page_content(mock_session, 123, "nonexistent")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_quiz_content(self, client, mock_session):
        """Test retrieving quiz content."""
        mock_quiz = {"description": "Quiz description"}

        with patch.object(client, '_get', return_value=mock_quiz):
            result = await client.get_quiz_content(mock_session, 123, 789)
            
            assert result == "Quiz description"
            client._get.assert_called_once_with(mock_session, "/courses/123/quizzes/789")

    @pytest.mark.asyncio
    async def test_get_file_content(self, client, mock_session):
        """Test retrieving file content."""
        mock_file_info = {"url": "https://example.com/file.txt"}
        mock_file_response = Mock()
        mock_file_response.status = 200
        mock_file_response.text = AsyncMock(return_value="File content")

        with patch.object(client, '_get', return_value=mock_file_info):
            # Create a proper async context manager mock
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_file_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session.get.return_value = mock_cm
            
            result = await client.get_file_content(mock_session, 456)
            
            assert result == "File content"

    @pytest.mark.asyncio
    async def test_fetch_module_item_content_page(self, client, mock_session):
        """Test fetching content for a Page module item."""
        module_item = {"type": "Page", "page_url": "test-page"}
        
        with patch.object(client, 'get_page_content', return_value="Page content"):
            result = await client.fetch_module_item_content(mock_session, 123, module_item)
            
            assert result == "Page content"

    @pytest.mark.asyncio
    async def test_fetch_module_item_content_file(self, client, mock_session):
        """Test fetching content for a File module item."""
        module_item = {"type": "File", "content_id": 789}
        
        with patch.object(client, 'get_file_content', return_value="File content"):
            result = await client.fetch_module_item_content(mock_session, 123, module_item)
            
            assert result == "File content"

    @pytest.mark.asyncio
    async def test_fetch_module_item_content_unknown_type(self, client, mock_session):
        """Test fetching content for unknown module item type."""
        module_item = {"type": "Unknown"}
        
        result = await client.fetch_module_item_content(mock_session, 123, module_item)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_assignments(self, client, mock_session):
        """Test retrieving assignments with description processing."""
        mock_assignments = [
            {
                "name": "Assignment 1",
                "due_at": "2024-12-31T23:59:59Z",
                "description": "<p>This is a <strong>test</strong> assignment</p>"
            },
            {
                "name": "Assignment 2", 
                "due_at": None,
                "description": None
            }
        ]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_assignments
            
            result = await client.get_assignments(mock_session, 123)
            
            expected = [
                {
                    "name": "Assignment 1",
                    "due_at": "2024-12-31T23:59:59Z", 
                    "type": "assignment",
                    "description": "This is a test assignment"
                },
                {
                    "name": "Assignment 2",
                    "due_at": None,
                    "type": "assignment", 
                    "description": ""
                }
            ]
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_quizzes(self, client, mock_session):
        """Test retrieving quizzes with description processing."""
        mock_quizzes = [
            {
                "title": "Quiz 1",
                "due_at": "2024-12-31T23:59:59Z",
                "description": "<div><h2>Quiz Instructions</h2><p>Complete all questions</p></div>"
            },
            {
                "title": "Quiz 2",
                "due_at": None, 
                "description": ""
            }
        ]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_quizzes
            
            result = await client.get_quizzes(mock_session, 123)
            
            expected = [
                {
                    "name": "Quiz 1",
                    "due_at": "2024-12-31T23:59:59Z",
                    "type": "quiz",
                    "description": "Quiz Instructions Complete all questions"
                },
                {
                    "name": "Quiz 2", 
                    "due_at": None,
                    "type": "quiz",
                    "description": ""
                }
            ]
            assert result == expected

    def test_html_to_text_conversion(self, client):
        """Test HTML to text conversion helper method."""
        # Test with HTML content
        html_content = "<p>This is <strong>bold</strong> and <em>italic</em> text.</p>"
        result = client._html_to_text(html_content)
        assert result == "This is bold and italic text."
        
        # Test with None
        result = client._html_to_text(None)
        assert result == ""
        
        # Test with empty string
        result = client._html_to_text("")
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__])