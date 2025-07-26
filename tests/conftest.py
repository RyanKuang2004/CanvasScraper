import pytest
import os
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        'CANVAS_API_TOKEN': 'test_token_123'
    }):
        yield

@pytest.fixture
def sample_course_data():
    """Sample course data for testing."""
    return {
        "id": 12345,
        "name": "Test Course",
        "enrollments": [{"enrollment_state": "active"}]
    }

@pytest.fixture
def sample_module_data():
    """Sample module data for testing."""
    return {
        "id": 67890,
        "name": "Test Module",
        "position": 1
    }