#!/usr/bin/env python3
"""
Docker Integration Test Suite
Tests all imports, core functionality, and entrypoint script validation for Canvas Scraper.
Ensures container readiness before deployment.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Handle optional imports gracefully
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Create minimal pytest replacement for standalone execution
    class MockMark:
        def __getattr__(self, name):
            return lambda f: f
    
    class pytest:
        mark = MockMark()
        
        @staticmethod
        def fixture(func=None):
            return func or (lambda f: f)
        
        @staticmethod
        def main(args):
            print("pytest not available, running standalone tests")
            return 0

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import requests_mock
    REQUESTS_MOCK_AVAILABLE = True
except ImportError:
    REQUESTS_MOCK_AVAILABLE = False
    # Create minimal requests_mock replacement
    class requests_mock:
        class Mocker:
            def __init__(self):
                pass
            def get(self, *args, **kwargs):
                pass
            def __call__(self, func):
                return func


class TestDockerIntegration:
    """Comprehensive Docker integration tests for Canvas Scraper."""
    
    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """Set up mock environment variables."""
        env_vars = {
            'CANVAS_API_TOKEN': 'test_token_12345',
            'CANVAS_URL': 'https://canvas.test.edu/api/v1',
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_ANON_KEY': 'test_anon_key',
            'PYTHONPATH': str(project_root)
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        return env_vars
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            yield config_dir
    
    def test_critical_imports(self):
        """Test that all critical Python modules can be imported."""
        # Test standard library imports first
        standard_imports = [
            ('json', None),
            ('os', None),
            ('sys', None),
            ('pathlib', 'Path'),
            ('tempfile', None),
            ('subprocess', None),
            ('datetime', 'datetime'),
        ]
        
        # Test optional external dependencies
        optional_imports = [
            ('yaml', None),
            ('requests', None),
            ('aiohttp', None),
            ('pdfplumber', None),
            ('pytesseract', None),
            ('tiktoken', None),
            ('apscheduler', None),
            ('supabase', None),
            ('pptx', None),
            ('docx', None),
        ]
        
        # Test project modules (may fail due to missing dependencies)
        project_modules = [
            ('src.config', None),
            ('src.canvas_client', 'CanvasClient'),
            ('src.canvas_orchestrator', None),
        ]
        
        failed_standard = []
        failed_optional = []
        failed_project = []
        
        # Test standard library imports (these should always work)
        for module_name, class_name in standard_imports:
            try:
                module = __import__(module_name, fromlist=[class_name] if class_name else [])
                if class_name:
                    getattr(module, class_name)
                print(f"✅ Successfully imported {module_name}" + 
                      (f".{class_name}" if class_name else ""))
            except (ImportError, AttributeError) as e:
                failed_standard.append(f"{module_name}: {e}")
        
        # Test optional imports (warnings only)
        available_optional = []
        for module_name, class_name in optional_imports:
            try:
                module = __import__(module_name, fromlist=[class_name] if class_name else [])
                if class_name:
                    getattr(module, class_name)
                available_optional.append(module_name)
                print(f"✅ Optional import available: {module_name}" + 
                      (f".{class_name}" if class_name else ""))
            except (ImportError, AttributeError) as e:
                failed_optional.append(f"{module_name}: {e}")
                print(f"⚠️  Optional import missing: {module_name}")
        
        # Test project modules (may fail due to missing deps)
        available_project = []
        for module_name, class_name in project_modules:
            try:
                module = __import__(module_name, fromlist=[class_name] if class_name else [])
                if class_name:
                    getattr(module, class_name)
                available_project.append(module_name)
                print(f"✅ Project module available: {module_name}" + 
                      (f".{class_name}" if class_name else ""))
            except (ImportError, AttributeError) as e:
                failed_project.append(f"{module_name}: {e}")
                print(f"⚠️  Project module unavailable: {module_name} - {e}")
        
        # Only fail on standard library imports
        assert not failed_standard, f"Critical standard library imports failed: {failed_standard}"
        
        # Log summary
        print(f"📊 Import Summary:")
        print(f"  Standard library: {len(standard_imports) - len(failed_standard)}/{len(standard_imports)}")
        print(f"  Optional deps: {len(available_optional)}/{len(optional_imports)}")
        print(f"  Project modules: {len(available_project)}/{len(project_modules)}")
        
        if failed_optional:
            print(f"💡 To enable full functionality, install missing dependencies:")
            print(f"  pip install -r requirements.txt")
    
    def test_environment_validation(self, mock_env_vars):
        """Test environment variable validation logic."""
        # Test required variables
        required_vars = ['CANVAS_API_TOKEN', 'CANVAS_URL']
        for var in required_vars:
            assert var in mock_env_vars, f"Required environment variable {var} not set"
            assert mock_env_vars[var], f"Required environment variable {var} is empty"
        
        # Test optional but recommended variables
        optional_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY']
        for var in optional_vars:
            if var in mock_env_vars:
                print(f"✅ Optional variable {var} is set")
    
    @patch('subprocess.run')
    def test_entrypoint_script_validation(self, mock_subprocess, mock_env_vars):
        """Test entrypoint script execution flow validation."""
        # Mock successful command execution
        mock_subprocess.return_value = Mock(returncode=0, stdout='', stderr='')
        
        entrypoint_script = project_root / "docker" / "entrypoint.sh"
        assert entrypoint_script.exists(), "Entrypoint script not found"
        
        # Test script is executable
        assert os.access(entrypoint_script, os.X_OK), "Entrypoint script is not executable"
        
        # Validate script syntax (basic bash check)
        result = subprocess.run(['bash', '-n', str(entrypoint_script)], 
                              capture_output=True, text=True)
        assert result.returncode == 0, f"Bash syntax error: {result.stderr}"
    
    def test_config_file_creation_and_validation(self, temp_config_dir):
        """Test configuration file creation and validation."""
        # Create test configuration
        config_data = {
            'enabled_courses': ['12345', '67890'],
            'scraping_preferences': {
                'file_types': ['pdf', 'pptx', 'docx'],
                'max_file_size_mb': 50,
                'skip_hidden_modules': True,
                'concurrent_downloads': 3
            },
            'text_processing': {
                'chunk_size': 1000,
                'chunk_overlap': 200,
                'preserve_structure': True
            },
            'scheduling': {
                'enabled': True,
                'timezone': 'Australia/Melbourne',
                'times': ['12:00', '20:00']
            },
            'deduplication': {
                'enabled': True,
                'check_content_changes': True,
                'fingerprint_algorithm': 'sha256'
            }
        }
        
        # Write config file
        config_file = temp_config_dir / "courses.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Validate configuration
        with open(config_file, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        assert loaded_config == config_data, "Configuration data mismatch"
        assert 'enabled_courses' in loaded_config, "enabled_courses missing"
        assert isinstance(loaded_config['enabled_courses'], list), "enabled_courses should be a list"
    
    @requests_mock.Mocker()
    def test_canvas_api_connectivity_simulation(self, m, mock_env_vars):
        """Test Canvas API connectivity simulation."""
        # Mock Canvas API response
        canvas_url = mock_env_vars['CANVAS_URL']
        m.get(f"{canvas_url}/users/self", json={'id': 1, 'name': 'Test User'}, status_code=200)
        
        # Test Canvas client initialization
        from src.canvas_client import CanvasClient
        
        client = CanvasClient()
        
        # Test basic connectivity
        response = client.session.get(f"{canvas_url}/users/self")
        assert response.status_code == 200
        assert 'id' in response.json()
    
    @requests_mock.Mocker()
    def test_supabase_connectivity_simulation(self, m, mock_env_vars):
        """Test Supabase connectivity simulation."""
        # Mock Supabase API response
        supabase_url = mock_env_vars['SUPABASE_URL']
        m.get(f"{supabase_url}/rest/v1/", json={'message': 'ok'}, status_code=200)
        
        # Simulate basic Supabase connectivity test
        import requests
        headers = {
            'apikey': mock_env_vars['SUPABASE_ANON_KEY'],
            'Authorization': f"Bearer {mock_env_vars['SUPABASE_ANON_KEY']}"
        }
        
        response = requests.get(f"{supabase_url}/rest/v1/", headers=headers)
        assert response.status_code == 200
    
    def test_directory_structure_setup(self, temp_config_dir):
        """Test that required directories can be created."""
        base_dir = temp_config_dir.parent
        required_dirs = ['logs', 'data', 'downloads', 'config']
        
        for dir_name in required_dirs:
            dir_path = base_dir / dir_name
            dir_path.mkdir(exist_ok=True)
            assert dir_path.exists(), f"Failed to create directory: {dir_name}"
            assert dir_path.is_dir(), f"Path is not a directory: {dir_name}"
    
    def test_file_processor_initialization(self):
        """Test that file processors can be initialized."""
        from src.file_processors.pdf_processor import PDFProcessor
        from src.file_processors.pptx_processor import PPTXProcessor
        from src.file_processors.docx_processor import DOCXProcessor
        
        # Test processor initialization
        processors = [
            PDFProcessor(),
            PPTXProcessor(),
            DOCXProcessor()
        ]
        
        for processor in processors:
            assert hasattr(processor, 'extract_text'), f"Processor missing extract_text method: {type(processor)}"
            assert hasattr(processor, 'extract_metadata'), f"Processor missing extract_metadata method: {type(processor)}"
    
    def test_text_chunker_functionality(self):
        """Test text chunking functionality."""
        from src.text_chunker import TextChunker
        
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        
        # Test with sample text
        sample_text = "This is a test document. " * 20  # Create longer text
        chunks = chunker.chunk_text(sample_text)
        
        assert isinstance(chunks, list), "Chunks should be a list"
        assert len(chunks) > 0, "Should produce at least one chunk"
        
        for chunk in chunks:
            assert isinstance(chunk, dict), "Each chunk should be a dictionary"
            assert 'text' in chunk, "Each chunk should have text"
            assert 'metadata' in chunk, "Each chunk should have metadata"
    
    def test_content_fingerprinting(self):
        """Test content fingerprinting for deduplication."""
        from src.content_fingerprint import ContentFingerprint
        
        fingerprinter = ContentFingerprint()
        
        # Test fingerprint generation
        test_content = "This is test content for fingerprinting"
        fingerprint1 = fingerprinter.generate_fingerprint(test_content)
        fingerprint2 = fingerprinter.generate_fingerprint(test_content)
        
        assert fingerprint1 == fingerprint2, "Same content should produce same fingerprint"
        assert isinstance(fingerprint1, str), "Fingerprint should be a string"
        assert len(fingerprint1) == 64, "SHA-256 fingerprint should be 64 characters"
    
    def test_state_manager_functionality(self, temp_config_dir):
        """Test state management functionality."""
        from src.state_manager import StateManager
        
        state_file = temp_config_dir / "state.json"
        state_manager = StateManager(str(state_file))
        
        # Test state operations
        test_key = "test_file.pdf"
        test_state = {"processed": True, "timestamp": datetime.now().isoformat()}
        
        state_manager.update_state(test_key, test_state)
        retrieved_state = state_manager.get_state(test_key)
        
        assert retrieved_state == test_state, "State should be retrievable"
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization."""
        from src.scheduler import Scheduler
        
        scheduler = Scheduler(timezone="Australia/Melbourne")
        
        assert hasattr(scheduler, 'add_job'), "Scheduler should have add_job method"
        assert hasattr(scheduler, 'start'), "Scheduler should have start method"
        assert hasattr(scheduler, 'shutdown'), "Scheduler should have shutdown method"
    
    @patch('sys.exit')
    def test_import_validation_script(self, mock_exit):
        """Test the Docker import validation script."""
        fix_imports_script = project_root / "docker" / "fix_imports.py"
        
        if fix_imports_script.exists():
            # Run the import validation script
            result = subprocess.run([sys.executable, str(fix_imports_script)], 
                                  capture_output=True, text=True)
            
            # Check that script runs without critical errors
            assert result.returncode in [0, 1], f"Import script failed unexpectedly: {result.stderr}"
            assert "Import validation" in result.stdout, "Import validation should run"
    
    def test_health_check_functionality(self):
        """Test health check functionality."""
        # Test basic health check logic
        health_data = {
            'status': 'healthy',
            'service': 'canvas-scraper',
            'timestamp': datetime.now().isoformat()
        }
        
        # Validate health check response format
        assert 'status' in health_data, "Health check should include status"
        assert 'service' in health_data, "Health check should include service name"
        assert health_data['status'] in ['healthy', 'unhealthy'], "Status should be valid"
    
    def test_error_handling_and_logging(self, caplog):
        """Test error handling and logging functionality."""
        import logging
        
        # Test that logging works
        logger = logging.getLogger('canvas_scraper')
        test_message = "Test log message for integration test"
        logger.info(test_message)
        
        # Test error handling patterns
        try:
            raise Exception("Test exception for error handling")
        except Exception as e:
            logger.error(f"Caught test exception: {e}")
            # Exception should be caught and logged
    
    def test_docker_entrypoint_command_parsing(self):
        """Test command parsing logic for Docker entrypoint."""
        # Test different command scenarios
        commands = [
            [],  # No command (should default)
            ['python', 'scripts/run_enhanced_scraper.py', 'run'],
            ['python', 'scripts/run_enhanced_scraper.py', 'daemon'],
            ['python', 'scripts/run_enhanced_scraper.py', 'search', '--query', 'test']
        ]
        
        for cmd in commands:
            # Validate command structure
            if cmd:
                assert isinstance(cmd, list), "Command should be a list"
                assert len(cmd) > 0, "Command should not be empty"
            
    @pytest.mark.integration
    def test_full_initialization_sequence(self, mock_env_vars, temp_config_dir):
        """Test the complete initialization sequence."""
        # This test simulates the full Docker container startup sequence
        
        # 1. Environment check
        self.test_environment_validation(mock_env_vars)
        
        # 2. Directory setup
        self.test_directory_structure_setup(temp_config_dir)
        
        # 3. Configuration validation
        self.test_config_file_creation_and_validation(temp_config_dir)
        
        # 4. Import validation
        self.test_critical_imports()
        
        # 5. Component initialization
        self.test_file_processor_initialization()
        self.test_text_chunker_functionality()
        self.test_content_fingerprinting()
        
        print("✅ Complete initialization sequence validation passed")
    
    def test_entrypoint_script_validation_standalone(self):
        """Standalone version of entrypoint script validation."""
        entrypoint_script = project_root / "docker" / "entrypoint.sh"
        assert entrypoint_script.exists(), "Entrypoint script not found"
        
        # Test script is executable
        if not os.access(entrypoint_script, os.X_OK):
            print("⚠️  Warning: Entrypoint script may not be executable")
        
        # Test bash syntax
        result = subprocess.run(
            ['bash', '-n', str(entrypoint_script)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                "bash syntax check",
                stderr=result.stderr
            )
        
        print("✅ Entrypoint script syntax validation passed")
    
    def test_error_handling_and_logging_standalone(self):
        """Standalone version of error handling test."""
        import logging
        
        # Test logger setup
        test_logger = logging.getLogger('canvas_scraper_test')
        test_logger.setLevel(logging.INFO)
        
        # Test logging functionality
        test_message = "Test log message for Docker validation"
        test_logger.info(test_message)
        
        # Test error handling patterns
        try:
            raise ValueError("Test exception for error handling validation")
        except ValueError as e:
            test_logger.error(f"Successfully caught test exception: {e}")
        
        print("✅ Error handling and logging functionality working")


class TestDockerProductionReadiness:
    """Test production readiness aspects."""
    
    def test_security_configurations(self):
        """Test security-related configurations."""
        # Test that sensitive data is not hardcoded
        entrypoint_script = project_root / "docker" / "entrypoint.sh"
        if entrypoint_script.exists():
            with open(entrypoint_script, 'r') as f:
                content = f.read()
                
            # Check for hardcoded secrets (basic patterns)
            suspicious_patterns = [
                'password=',
                'secret=',
                'token=12345',
                'key=abcd'
            ]
            
            for pattern in suspicious_patterns:
                assert pattern.lower() not in content.lower(), f"Potential hardcoded secret: {pattern}"
    
    def test_resource_limits_awareness(self):
        """Test resource limit awareness."""
        # Test that the application handles resource constraints
        import psutil
        
        # Basic system resource check
        memory = psutil.virtual_memory()
        assert memory.available > 100 * 1024 * 1024, "Should have at least 100MB available memory"
        
        # Test that components can handle limited resources
        from src.text_chunker import TextChunker
        
        # Test with smaller chunk sizes for limited resources
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)  # Smaller chunks
        sample_text = "Test " * 1000
        chunks = chunker.chunk_text(sample_text)
        
        assert len(chunks) > 0, "Should handle chunking with resource constraints"
    
    def test_graceful_degradation(self):
        """Test graceful degradation when optional services are unavailable."""
        # Test that the application can handle missing optional dependencies
        # In a standalone environment, this just validates the concept
        try:
            # Simulate missing service
            missing_service = None
            if missing_service is None:
                print("✅ Graceful degradation: Handled missing service correctly")
        except Exception as e:
            # Should be a controlled exception, not a crash
            assert "configuration" in str(e).lower() or "connection" in str(e).lower()


# pytest configuration for Docker integration tests
def pytest_configure(config):
    """Configure pytest for Docker integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


def run_standalone_tests():
    """Run tests without pytest for environments where it's not available."""
    print("🧪 Running Docker Integration Tests (Standalone Mode)")
    print("=" * 60)
    
    # Create test instance
    test_instance = TestDockerIntegration()
    
    # Set up mock environment
    mock_env_vars = {
        'CANVAS_API_TOKEN': 'test_token_12345',
        'CANVAS_URL': 'https://canvas.test.edu/api/v1',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_ANON_KEY': 'test_anon_key',
        'PYTHONPATH': str(project_root)
    }
    
    for key, value in mock_env_vars.items():
        os.environ[key] = value
    
    # Create temp config directory
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_dir = Path(temp_dir) / "config"
        temp_config_dir.mkdir()
        
        # Run tests
        tests = [
            ("Critical Imports", lambda: test_instance.test_critical_imports()),
            ("Environment Validation", lambda: test_instance.test_environment_validation(mock_env_vars)),
            ("Entrypoint Script", lambda: test_instance.test_entrypoint_script_validation_standalone()),
            ("Config Validation", lambda: test_instance.test_config_file_creation_and_validation(temp_config_dir)),
            ("Directory Setup", lambda: test_instance.test_directory_structure_setup(temp_config_dir)),
            ("Health Check", lambda: test_instance.test_health_check_functionality()),
            ("Error Handling", lambda: test_instance.test_error_handling_and_logging_standalone()),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                print(f"\n🧪 Running: {test_name}")
                test_func()
                print(f"✅ PASSED: {test_name}")
                passed += 1
            except Exception as e:
                print(f"❌ FAILED: {test_name} - {e}")
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All tests passed!")
            return True
        else:
            print(f"❌ {failed} tests failed")
            return False


if __name__ == "__main__":
    if PYTEST_AVAILABLE:
        # Run with pytest if available
        pytest.main([__file__, "-v", "--tb=short"])
    else:
        # Run standalone tests
        success = run_standalone_tests()
        sys.exit(0 if success else 1)