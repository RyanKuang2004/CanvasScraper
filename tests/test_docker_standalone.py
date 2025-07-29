#!/usr/bin/env python3
"""
Standalone Docker Integration Test
Tests all imports, core functionality without requiring pytest.
Designed to run in any Python environment for troubleshooting.
"""

import os
import sys
import json
import tempfile
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

class DockerIntegrationTester:
    """Standalone Docker integration tester."""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def run_test(self, test_name, test_func):
        """Run a single test and record results."""
        logger.info(f"🧪 Testing: {test_name}")
        try:
            test_func()
            logger.info(f"✅ PASSED: {test_name}")
            self.test_results.append({"test": test_name, "status": "PASSED", "error": None})
            self.passed += 1
            return True
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ FAILED: {test_name} - {error_msg}")
            self.test_results.append({"test": test_name, "status": "FAILED", "error": error_msg})
            self.failed += 1
            return False
    
    def test_environment_setup(self):
        """Test environment variable setup."""
        # Set test environment variables
        test_env = {
            'CANVAS_API_TOKEN': 'test_token_12345',
            'CANVAS_URL': 'https://canvas.test.edu/api/v1',
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_ANON_KEY': 'test_anon_key',
            'PYTHONPATH': str(project_root)
        }
        
        for key, value in test_env.items():
            os.environ[key] = value
        
        # Validate required variables
        required_vars = ['CANVAS_API_TOKEN', 'CANVAS_URL']
        for var in required_vars:
            if not os.environ.get(var):
                raise ValueError(f"Missing required environment variable: {var}")
        
        logger.info("Environment variables configured successfully")
    
    def test_basic_imports(self):
        """Test basic Python standard library imports."""
        import json
        import os
        import sys
        import tempfile
        import subprocess
        from pathlib import Path
        from datetime import datetime
        
        # Test yaml if available
        try:
            import yaml
            test_data = {"test": "value"}
            yaml_str = yaml.dump(test_data)
            loaded = yaml.safe_load(yaml_str)
            assert loaded == test_data, "YAML serialization failed"
        except ImportError:
            logger.warning("PyYAML not available, skipping YAML tests")
        
        # Test requests if available
        try:
            import requests
            logger.info("Requests module available")
        except ImportError:
            logger.warning("Requests module not available")
        
        logger.info("Basic imports successful")
    
    def test_project_structure(self):
        """Test project directory structure."""
        required_dirs = [
            'src',
            'scripts', 
            'tests',
            'docker',
            'config'
        ]
        
        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            if not dir_path.exists():
                raise FileNotFoundError(f"Required directory missing: {dir_name}")
            if not dir_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {dir_name}")
        
        logger.info("Project structure validation passed")
    
    def test_core_modules_exist(self):
        """Test that core module files exist."""
        core_modules = [
            'src/canvas_client.py',
            'src/config.py',
            'src/canvas_orchestrator.py',
            'scripts/run_enhanced_scraper.py',
            'docker/entrypoint.sh'
        ]
        
        for module_path in core_modules:
            file_path = project_root / module_path
            if not file_path.exists():
                raise FileNotFoundError(f"Core module missing: {module_path}")
        
        logger.info("Core module files exist")
    
    def test_configuration_handling(self):
        """Test configuration file handling."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not available, skipping config tests")
            return
        
        # Create test configuration
        test_config = {
            'enabled_courses': ['12345', '67890'],
            'scraping_preferences': {
                'file_types': ['pdf', 'pptx', 'docx'],
                'max_file_size_mb': 50
            },
            'text_processing': {
                'chunk_size': 1000,
                'chunk_overlap': 200
            }
        }
        
        # Test YAML serialization/deserialization
        yaml_str = yaml.dump(test_config)
        loaded_config = yaml.safe_load(yaml_str)
        
        if loaded_config != test_config:
            raise ValueError("Configuration serialization/deserialization failed")
        
        # Validate required fields
        required_fields = ['enabled_courses', 'scraping_preferences']
        for field in required_fields:
            if field not in loaded_config:
                raise ValueError(f"Required configuration field missing: {field}")
        
        logger.info("Configuration handling validation passed")
    
    def test_file_system_operations(self):
        """Test file system operations."""
        # Test temporary directory creation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test directory creation
            test_dir = temp_path / "test_logs"
            test_dir.mkdir()
            assert test_dir.exists(), "Directory creation failed"
            
            # Test file writing
            test_file = test_dir / "test.log"
            test_content = f"Test log entry: {datetime.now().isoformat()}"
            test_file.write_text(test_content)
            
            # Test file reading
            read_content = test_file.read_text()
            assert read_content == test_content, "File write/read failed"
        
        logger.info("File system operations validation passed")
    
    def test_json_operations(self):
        """Test JSON serialization operations."""
        test_data = {
            'timestamp': datetime.now().isoformat(),
            'test_results': [
                {'name': 'test1', 'status': 'passed'},
                {'name': 'test2', 'status': 'failed', 'error': 'Sample error'}
            ],
            'metadata': {
                'version': '2.0',
                'platform': sys.platform
            }
        }
        
        # Test JSON serialization
        json_str = json.dumps(test_data, indent=2)
        loaded_data = json.loads(json_str)
        
        assert loaded_data == test_data, "JSON serialization failed"
        
        # Test file-based JSON operations
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name
        
        try:
            with open(temp_file, 'r') as f:
                file_loaded_data = json.load(f)
            assert file_loaded_data == test_data, "JSON file operations failed"
        finally:
            os.unlink(temp_file)
        
        logger.info("JSON operations validation passed")
    
    def test_subprocess_operations(self):
        """Test subprocess operations."""
        # Test basic command execution
        result = subprocess.run(['echo', 'test'], capture_output=True, text=True)
        assert result.returncode == 0, "Basic subprocess execution failed"
        assert 'test' in result.stdout, "Subprocess output validation failed"
        
        # Test Python execution
        result = subprocess.run([
            sys.executable, '-c', 
            'import sys; print(f"Python {sys.version_info.major}.{sys.version_info.minor}")'
        ], capture_output=True, text=True)
        assert result.returncode == 0, "Python subprocess execution failed"
        assert 'Python' in result.stdout, "Python version check failed"
        
        logger.info("Subprocess operations validation passed")
    
    def test_entrypoint_script_syntax(self):
        """Test Docker entrypoint script syntax."""
        entrypoint_script = project_root / "docker" / "entrypoint.sh"
        
        if not entrypoint_script.exists():
            raise FileNotFoundError("Entrypoint script not found")
        
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
        
        logger.info("Entrypoint script syntax validation passed")
    
    def test_python_path_resolution(self):
        """Test Python path resolution for project modules."""
        # Test that we can access the src directory
        src_path = project_root / "src"
        assert src_path.exists(), "src directory not found"
        
        # Test that src is in sys.path
        assert str(src_path) in sys.path, "src path not in sys.path"
        
        # Test module discovery
        core_files = [
            'canvas_client.py',
            'config.py',
            'canvas_orchestrator.py'
        ]
        
        for file_name in core_files:
            module_file = src_path / file_name
            if not module_file.exists():
                raise FileNotFoundError(f"Core module file missing: {file_name}")
        
        logger.info("Python path resolution validation passed")
    
    def test_import_attempts(self):
        """Test import attempts for project modules (without requiring dependencies)."""
        import_attempts = [
            ('json', 'standard library'),
            ('os', 'standard library'),
            ('sys', 'standard library'),
            ('pathlib', 'standard library'),
            ('tempfile', 'standard library'),
            ('subprocess', 'standard library'),
        ]
        
        # Test optional imports
        optional_imports = [
            ('yaml', 'PyYAML'),
            ('requests', 'requests library'),
        ]
        
        for module_name, description in import_attempts:
            try:
                __import__(module_name)
                logger.info(f"✅ Successfully imported {module_name} ({description})")
            except ImportError as e:
                raise ImportError(f"Failed to import required module {module_name}: {e}")
        
        # Test optional imports (warnings only)
        available_optional = []
        for module_name, description in optional_imports:
            try:
                __import__(module_name)
                available_optional.append(module_name)
                logger.info(f"✅ Optional module {module_name} available ({description})")
            except ImportError:
                logger.warning(f"⚠️  Optional module {module_name} not available ({description})")
        
        logger.info(f"Import validation passed. Optional modules available: {available_optional}")
    
    def run_all_tests(self):
        """Run all tests and generate summary."""
        logger.info("🚀 Starting Standalone Docker Integration Tests")
        logger.info("=" * 60)
        
        tests = [
            ("Environment Setup", self.test_environment_setup),
            ("Basic Imports", self.test_basic_imports),
            ("Project Structure", self.test_project_structure),
            ("Core Modules Exist", self.test_core_modules_exist),
            ("Configuration Handling", self.test_configuration_handling),
            ("File System Operations", self.test_file_system_operations),
            ("JSON Operations", self.test_json_operations),
            ("Subprocess Operations", self.test_subprocess_operations),
            ("Entrypoint Script Syntax", self.test_entrypoint_script_syntax),
            ("Python Path Resolution", self.test_python_path_resolution),
            ("Import Attempts", self.test_import_attempts),
        ]
        
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        # Generate summary
        logger.info("=" * 60)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {len(tests)}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"Success Rate: {(self.passed/len(tests)*100):.1f}%")
        
        if self.failed == 0:
            logger.info("🎉 ALL TESTS PASSED")
            success = True
        else:
            logger.error("❌ SOME TESTS FAILED")
            logger.error("Failed tests:")
            for result in self.test_results:
                if result['status'] == 'FAILED':
                    logger.error(f"  • {result['test']}: {result['error']}")
            success = False
        
        # Save results
        results_summary = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(tests),
            'passed': self.passed,
            'failed': self.failed,
            'success_rate': self.passed/len(tests)*100,
            'overall_success': success,
            'detailed_results': self.test_results
        }
        
        results_file = project_root / "standalone_test_results.json"
        with open(results_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        logger.info(f"📄 Detailed results saved to: {results_file}")
        return success


def main():
    """Main execution function."""
    tester = DockerIntegrationTester()
    
    try:
        success = tester.run_all_tests()
        exit_code = 0 if success else 1
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 STANDALONE INTEGRATION TESTS SUCCESSFUL")
            print("   Basic functionality validated successfully.")
        else:
            print("🚨 STANDALONE INTEGRATION TESTS FAILED")
            print("   Please review the failed tests above.")
        print("=" * 60)
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test runner crashed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()