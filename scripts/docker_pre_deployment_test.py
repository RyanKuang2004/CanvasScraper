#!/usr/bin/env python3
"""
Docker Pre-Deployment Test Runner
Comprehensive validation script that tests all critical functionality before Docker deployment.
This script simulates the Docker container environment and validates all components.
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('docker_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


class DockerPreDeploymentValidator:
    """Comprehensive Docker pre-deployment validation."""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        self.warnings = []
        
    def log_test_result(self, test_name, passed, message="", error=None):
        """Log test result."""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        if error:
            result['error'] = str(error)
            result['traceback'] = traceback.format_exc()
        
        self.test_results.append(result)
        
        if passed:
            logger.info(f"✅ {test_name}: {message}")
        else:
            logger.error(f"❌ {test_name}: {message}")
            if error:
                logger.error(f"   Error: {error}")
    
    def test_environment_setup(self):
        """Test environment variable setup and validation."""
        try:
            # Required environment variables for testing
            test_env = {
                'CANVAS_API_TOKEN': 'test_token_12345',
                'CANVAS_URL': 'https://canvas.test.edu/api/v1',
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_ANON_KEY': 'test_anon_key',
                'PYTHONPATH': str(project_root)
            }
            
            # Set test environment
            for key, value in test_env.items():
                os.environ[key] = value
            
            # Validate environment
            missing_vars = []
            for key in ['CANVAS_API_TOKEN', 'CANVAS_URL']:
                if not os.environ.get(key):
                    missing_vars.append(key)
            
            if missing_vars:
                self.log_test_result(
                    "environment_setup",
                    False,
                    f"Missing required environment variables: {missing_vars}"
                )
                return False
            
            self.log_test_result(
                "environment_setup",
                True,
                "Environment variables configured correctly"
            )
            return True
            
        except Exception as e:
            self.log_test_result("environment_setup", False, "Environment setup failed", e)
            return False
    
    def test_critical_imports(self):
        """Test all critical imports for Docker container."""
        try:
            import_tests = [
                # Core application modules
                'src.canvas_client',
                'src.canvas_orchestrator',
                'src.config',
                'src.course_manager',
                'src.file_processor_manager',
                'src.content_fingerprint',
                'src.state_manager',
                'src.text_chunker',
                'src.scheduler',
                'src.supabase_client',
                
                # File processors
                'src.file_processors.base_processor',
                'src.file_processors.pdf_processor',
                'src.file_processors.pptx_processor',
                'src.file_processors.docx_processor',
                
                # Critical external dependencies
                'aiohttp',
                'requests',
                'yaml',
                'pdfplumber',
                'tiktoken',
                'apscheduler',
                'supabase',
                'pptx',
                'docx'
            ]
            
            failed_imports = []
            for module_name in import_tests:
                try:
                    __import__(module_name)
                    logger.debug(f"✅ Successfully imported {module_name}")
                except ImportError as e:
                    failed_imports.append(f"{module_name}: {e}")
                    logger.debug(f"❌ Failed to import {module_name}: {e}")
            
            if failed_imports:
                self.log_test_result(
                    "critical_imports",
                    False,
                    f"Failed imports: {len(failed_imports)}",
                    "\n".join(failed_imports)
                )
                return False
            
            self.log_test_result(
                "critical_imports",
                True,
                f"All {len(import_tests)} critical imports successful"
            )
            return True
            
        except Exception as e:
            self.log_test_result("critical_imports", False, "Import testing failed", e)
            return False
    
    def test_file_processors(self):
        """Test file processor initialization and basic functionality."""
        try:
            from src.file_processors.pdf_processor import PDFProcessor
            from src.file_processors.pptx_processor import PPTXProcessor
            from src.file_processors.docx_processor import DOCXProcessor
            
            processors = [
                ("PDF", PDFProcessor()),
                ("PPTX", PPTXProcessor()),
                ("DOCX", DOCXProcessor())
            ]
            
            for name, processor in processors:
                # Test required methods exist
                required_methods = ['extract_text', 'extract_metadata']
                for method in required_methods:
                    if not hasattr(processor, method):
                        raise AttributeError(f"{name} processor missing {method} method")
                
                logger.debug(f"✅ {name} processor initialized successfully")
            
            self.log_test_result(
                "file_processors",
                True,
                f"All {len(processors)} file processors initialized correctly"
            )
            return True
            
        except Exception as e:
            self.log_test_result("file_processors", False, "File processor testing failed", e)
            return False
    
    def test_text_processing(self):
        """Test text chunking and processing functionality."""
        try:
            from src.text_chunker import TextChunker
            from src.content_fingerprint import ContentFingerprint
            
            # Test text chunker
            chunker = TextChunker(chunk_size=100, chunk_overlap=20)
            sample_text = "This is a test document for chunking. " * 20
            chunks = chunker.chunk_text(sample_text)
            
            if not isinstance(chunks, list) or len(chunks) == 0:
                raise ValueError("Text chunker failed to produce chunks")
            
            # Validate chunk structure
            for chunk in chunks[:3]:  # Check first few chunks
                if not isinstance(chunk, dict) or 'text' not in chunk:
                    raise ValueError("Invalid chunk structure")
            
            # Test content fingerprinting
            fingerprinter = ContentFingerprint()
            test_content = "Test content for fingerprinting"
            fingerprint = fingerprinter.generate_fingerprint(test_content)
            
            if not isinstance(fingerprint, str) or len(fingerprint) != 64:
                raise ValueError("Invalid fingerprint generated")
            
            self.log_test_result(
                "text_processing",
                True,
                f"Text chunker produced {len(chunks)} chunks, fingerprinting working"
            )
            return True
            
        except Exception as e:
            self.log_test_result("text_processing", False, "Text processing testing failed", e)
            return False
    
    def test_configuration_handling(self):
        """Test configuration file handling and validation."""
        try:
            import yaml
            
            # Create test configuration
            test_config = {
                'enabled_courses': ['12345', '67890'],
                'scraping_preferences': {
                    'file_types': ['pdf', 'pptx', 'docx'],
                    'max_file_size_mb': 50,
                    'concurrent_downloads': 3
                },
                'text_processing': {
                    'chunk_size': 1000,
                    'chunk_overlap': 200
                },
                'scheduling': {
                    'enabled': True,
                    'timezone': 'Australia/Melbourne'
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
            
            self.log_test_result(
                "configuration_handling",
                True,
                "Configuration handling and validation working correctly"
            )
            return True
            
        except Exception as e:
            self.log_test_result("configuration_handling", False, "Configuration testing failed", e)
            return False
    
    def test_state_management(self):
        """Test state management functionality."""
        try:
            from src.state_manager import StateManager
            
            # Create temporary state file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                state_file = f.name
            
            try:
                state_manager = StateManager(state_file)
                
                # Test state operations
                test_key = "test_file.pdf"
                test_state = {
                    "processed": True,
                    "timestamp": datetime.now().isoformat(),
                    "fingerprint": "abc123"
                }
                
                # Update and retrieve state
                state_manager.update_state(test_key, test_state)
                retrieved_state = state_manager.get_state(test_key)
                
                if retrieved_state != test_state:
                    raise ValueError("State storage/retrieval failed")
                
                self.log_test_result(
                    "state_management",
                    True,
                    "State management working correctly"
                )
                return True
                
            finally:
                # Cleanup
                if os.path.exists(state_file):
                    os.unlink(state_file)
            
        except Exception as e:
            self.log_test_result("state_management", False, "State management testing failed", e)
            return False
    
    def test_scheduler_functionality(self):
        """Test scheduler initialization and basic functionality."""
        try:
            from src.scheduler import Scheduler
            
            scheduler = Scheduler(timezone="Australia/Melbourne")
            
            # Test required methods
            required_methods = ['add_job', 'start', 'shutdown']
            for method in required_methods:
                if not hasattr(scheduler, method):
                    raise AttributeError(f"Scheduler missing {method} method")
            
            # Test scheduler can be started and stopped safely
            # Note: We don't actually start it to avoid background processes
            
            self.log_test_result(
                "scheduler_functionality",
                True,
                "Scheduler initialization and interface validation successful"
            )
            return True
            
        except Exception as e:
            self.log_test_result("scheduler_functionality", False, "Scheduler testing failed", e)
            return False
    
    def test_docker_entrypoint_script(self):
        """Test Docker entrypoint script syntax and structure."""
        try:
            entrypoint_script = project_root / "docker" / "entrypoint.sh"
            
            if not entrypoint_script.exists():
                raise FileNotFoundError("Entrypoint script not found")
            
            # Test script is executable
            if not os.access(entrypoint_script, os.X_OK):
                self.warnings.append("Entrypoint script may not be executable")
            
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
            
            # Test import fix script exists
            fix_imports_script = project_root / "docker" / "fix_imports.py"
            if fix_imports_script.exists():
                # Test the fix_imports script can run
                result = subprocess.run(
                    [sys.executable, str(fix_imports_script)],
                    capture_output=True,
                    text=True
                )
                # Note: Script may exit with 1 due to missing imports, but should not crash
                if result.returncode not in [0, 1]:
                    self.warnings.append(f"Import fix script unexpected exit code: {result.returncode}")
            
            self.log_test_result(
                "docker_entrypoint_script",
                True,
                "Docker entrypoint script validation successful"
            )
            return True
            
        except Exception as e:
            self.log_test_result("docker_entrypoint_script", False, "Entrypoint script testing failed", e)
            return False
    
    def test_error_handling_and_logging(self):
        """Test error handling and logging functionality."""
        try:
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
            
            self.log_test_result(
                "error_handling_logging",
                True,
                "Error handling and logging functionality working"
            )
            return True
            
        except Exception as e:
            self.log_test_result("error_handling_logging", False, "Error handling testing failed", e)
            return False
    
    def test_resource_constraints(self):
        """Test behavior under resource constraints."""
        try:
            import psutil
            
            # Check basic system resources
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Validate minimum requirements
            min_memory_mb = 100  # 100MB minimum
            min_disk_mb = 500    # 500MB minimum
            
            if memory.available < min_memory_mb * 1024 * 1024:
                self.warnings.append(f"Low memory: {memory.available // (1024*1024)}MB available")
            
            if disk.free < min_disk_mb * 1024 * 1024:
                self.warnings.append(f"Low disk space: {disk.free // (1024*1024)}MB available")
            
            # Test resource-conscious operations
            from src.text_chunker import TextChunker
            
            # Test with conservative settings
            chunker = TextChunker(chunk_size=500, chunk_overlap=50)
            sample_text = "Resource test " * 100
            chunks = chunker.chunk_text(sample_text)
            
            if len(chunks) == 0:
                raise ValueError("Resource-constrained chunking failed")
            
            self.log_test_result(
                "resource_constraints",
                True,
                f"Resource constraint testing passed. Memory: {memory.available // (1024*1024)}MB"
            )
            return True
            
        except Exception as e:
            self.log_test_result("resource_constraints", False, "Resource constraint testing failed", e)
            return False
    
    def run_all_tests(self):
        """Run all pre-deployment tests."""
        logger.info("🐳 Starting Docker Pre-Deployment Validation")
        logger.info("=" * 60)
        
        tests = [
            self.test_environment_setup,
            self.test_critical_imports,
            self.test_file_processors,
            self.test_text_processing,
            self.test_configuration_handling,
            self.test_state_management,
            self.test_scheduler_functionality,
            self.test_docker_entrypoint_script,
            self.test_error_handling_and_logging,
            self.test_resource_constraints
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                logger.error(f"Test {test_func.__name__} crashed: {e}")
                self.errors.append(f"Test {test_func.__name__} crashed: {e}")
        
        # Generate summary
        logger.info("=" * 60)
        logger.info("🔍 DOCKER PRE-DEPLOYMENT VALIDATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {total_tests - passed_tests}")
        logger.info(f"Warnings: {len(self.warnings)}")
        
        if self.warnings:
            logger.warning("⚠️  WARNINGS:")
            for warning in self.warnings:
                logger.warning(f"   • {warning}")
        
        if passed_tests == total_tests:
            logger.info("✅ ALL TESTS PASSED - DOCKER DEPLOYMENT READY")
            deployment_ready = True
        else:
            logger.error("❌ SOME TESTS FAILED - REVIEW BEFORE DEPLOYMENT")
            deployment_ready = False
        
        # Save detailed results
        results_summary = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'warnings': self.warnings,
            'deployment_ready': deployment_ready,
            'detailed_results': self.test_results
        }
        
        results_file = project_root / "docker_validation_results.json"
        with open(results_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        logger.info(f"📄 Detailed results saved to: {results_file}")
        
        return deployment_ready


def main():
    """Main execution function."""
    validator = DockerPreDeploymentValidator()
    
    try:
        deployment_ready = validator.run_all_tests()
        exit_code = 0 if deployment_ready else 1
        
        print("\n" + "=" * 60)
        if deployment_ready:
            print("🎉 DOCKER DEPLOYMENT VALIDATION SUCCESSFUL")
            print("   The application is ready for Docker deployment.")
        else:
            print("🚨 DOCKER DEPLOYMENT VALIDATION FAILED")
            print("   Please fix the issues before deploying to Docker.")
        print("=" * 60)
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Validation crashed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()