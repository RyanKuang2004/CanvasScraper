#!/usr/bin/env python3
"""
CourseManager - Configuration-driven course selection and management

Handles course discovery, configuration loading, and selective processing
based on YAML configuration files.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import yaml
from datetime import datetime

from canvas_client import CanvasClient


@dataclass
class CourseConfig:
    """Configuration for a specific course"""
    course_id: int
    name: str
    enabled: bool
    modules: List[int] | str  # List of module IDs or "all"
    file_types: List[str]
    priority: str  # "high", "normal", "low"
    max_file_size_mb: int
    reason: Optional[str] = None  # Reason if disabled


@dataclass
class ScrapingPreferences:
    """Global scraping preferences"""
    max_concurrent_downloads: int
    max_concurrent_courses: int
    chunk_size: int
    chunk_overlap: int
    min_chunk_size: int
    supported_file_types: List[str]
    max_file_size_mb: int
    download_timeout_seconds: int
    skip_file_patterns: List[str]
    local_cache_days: int
    compress_large_files: bool
    extract_images: bool
    extract_tables: bool
    preserve_formatting: bool
    max_retries: int
    retry_delay_seconds: int
    exponential_backoff: bool


class CourseManager:
    """Manages course selection and configuration"""
    
    def __init__(self, config_path: Path = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path or Path("config/courses.yml")
        self.config_data: Dict[str, Any] = {}
        self.course_configs: Dict[int, CourseConfig] = {}
        self.preferences: Optional[ScrapingPreferences] = None
        self._last_loaded: Optional[datetime] = None
        
    async def load_configuration(self) -> bool:
        """Load course configuration from YAML file"""
        try:
            if not self.config_path.exists():
                self.logger.error(f"Configuration file not found: {self.config_path}")
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config_data = yaml.safe_load(file)
            
            # Parse course configurations
            self.course_configs = {}
            enabled_courses = self.config_data.get('enabled_courses', {})
            
            for course_id_str, config in enabled_courses.items():
                course_id = int(course_id_str)
                self.course_configs[course_id] = CourseConfig(
                    course_id=course_id,
                    name=config.get('name', f'Course {course_id}'),
                    enabled=config.get('enabled', True),
                    modules=config.get('modules', 'all'),
                    file_types=config.get('file_types', ['pdf']),
                    priority=config.get('priority', 'normal'),
                    max_file_size_mb=config.get('max_file_size_mb', 50),
                    reason=config.get('reason')
                )
            
            # Parse scraping preferences
            prefs = self.config_data.get('scraping_preferences', {})
            self.preferences = ScrapingPreferences(
                max_concurrent_downloads=prefs.get('max_concurrent_downloads', 5),
                max_concurrent_courses=prefs.get('max_concurrent_courses', 3),
                chunk_size=prefs.get('chunk_size', 1000),
                chunk_overlap=prefs.get('chunk_overlap', 200),
                min_chunk_size=prefs.get('min_chunk_size', 100),
                supported_file_types=prefs.get('supported_file_types', ['pdf', 'pptx', 'docx']),
                max_file_size_mb=prefs.get('max_file_size_mb', 50),
                download_timeout_seconds=prefs.get('download_timeout_seconds', 300),
                skip_file_patterns=prefs.get('skip_file_patterns', []),
                local_cache_days=prefs.get('local_cache_days', 7),
                compress_large_files=prefs.get('compress_large_files', True),
                extract_images=prefs.get('extract_images', False),
                extract_tables=prefs.get('extract_tables', True),
                preserve_formatting=prefs.get('preserve_formatting', True),
                max_retries=prefs.get('max_retries', 3),
                retry_delay_seconds=prefs.get('retry_delay_seconds', 5),
                exponential_backoff=prefs.get('exponential_backoff', True)
            )
            
            self._last_loaded = datetime.now()
            self.logger.info(f"Loaded configuration for {len(self.course_configs)} courses")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return False
    
    async def discover_available_courses(self, canvas_client: CanvasClient) -> List[Dict[str, Any]]:
        """Discover all available courses from Canvas"""
        try:
            courses = await canvas_client.get_active_courses()
            self.logger.info(f"Discovered {len(courses)} available courses")
            return courses
        except Exception as e:
            self.logger.error(f"Failed to discover courses: {e}")
            return []
    
    def get_enabled_courses(self) -> List[CourseConfig]:
        """Get list of enabled courses from configuration"""
        enabled = [config for config in self.course_configs.values() if config.enabled]
        self.logger.info(f"Found {len(enabled)} enabled courses")
        return enabled
    
    def get_course_config(self, course_id: int) -> Optional[CourseConfig]:
        """Get configuration for a specific course"""
        return self.course_configs.get(course_id)
    
    def is_course_enabled(self, course_id: int) -> bool:
        """Check if a course is enabled for scraping"""
        config = self.course_configs.get(course_id)
        return config is not None and config.enabled
    
    def should_process_file(self, course_id: int, file_info: Dict[str, Any]) -> bool:
        """Check if a file should be processed based on course configuration"""
        config = self.get_course_config(course_id)
        if not config or not config.enabled:
            return False
        
        # Check file type
        filename = file_info.get('display_name', '').lower()
        file_ext = filename.split('.')[-1] if '.' in filename else ''
        if file_ext not in config.file_types:
            return False
        
        # Check file size
        file_size_mb = file_info.get('size', 0) / (1024 * 1024)
        if file_size_mb > config.max_file_size_mb:
            self.logger.warning(f"File {filename} too large: {file_size_mb:.1f}MB > {config.max_file_size_mb}MB")
            return False
        
        # Check skip patterns
        for pattern in self.preferences.skip_file_patterns:
            if self._matches_pattern(filename, pattern):
                self.logger.debug(f"File {filename} matches skip pattern: {pattern}")
                return False
        
        return True
    
    def should_process_module(self, course_id: int, module_id: int) -> bool:
        """Check if a module should be processed based on course configuration"""
        config = self.get_course_config(course_id)
        if not config or not config.enabled:
            return False
        
        # If modules is "all", process all modules
        if config.modules == "all":
            return True
        
        # If modules is a list, check if module_id is in it
        if isinstance(config.modules, list):
            return module_id in config.modules
        
        return False
    
    def get_courses_by_priority(self) -> Dict[str, List[CourseConfig]]:
        """Group enabled courses by priority"""
        priorities = {"high": [], "normal": [], "low": []}
        
        for config in self.get_enabled_courses():
            priority = config.priority.lower()
            if priority in priorities:
                priorities[priority].append(config)
            else:
                priorities["normal"].append(config)
        
        return priorities
    
    async def validate_course_access(self, canvas_client: CanvasClient, course_id: int) -> bool:
        """Validate that we have access to a configured course"""
        try:
            # Try to fetch course modules to test access
            async with canvas_client._get_session() as session:
                modules = await canvas_client.get_modules(session, course_id)
                return modules is not None
        except Exception as e:
            self.logger.warning(f"Cannot access course {course_id}: {e}")
            return False
    
    def get_scheduling_config(self) -> Dict[str, Any]:
        """Get scheduling configuration"""
        return self.config_data.get('scheduling', {})
    
    def get_discovery_config(self) -> Dict[str, Any]:
        """Get course discovery configuration"""
        return self.config_data.get('discovery', {})
    
    async def update_course_config(self, course_id: int, updates: Dict[str, Any]) -> bool:
        """Update configuration for a specific course"""
        try:
            if course_id not in self.course_configs:
                self.logger.error(f"Course {course_id} not found in configuration")
                return False
            
            # Update in-memory configuration
            config = self.course_configs[course_id]
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # Update the YAML data
            course_data = self.config_data['enabled_courses'][str(course_id)]
            course_data.update(updates)
            
            # Save back to file
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(self.config_data, file, default_flow_style=False, sort_keys=False)
            
            self.logger.info(f"Updated configuration for course {course_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update course configuration: {e}")
            return False
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches a glob-style pattern"""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        enabled_courses = self.get_enabled_courses()
        
        return {
            'total_courses': len(self.course_configs),
            'enabled_courses': len(enabled_courses),
            'disabled_courses': len(self.course_configs) - len(enabled_courses),
            'course_priorities': {
                priority: len(courses) 
                for priority, courses in self.get_courses_by_priority().items()
            },
            'supported_file_types': self.preferences.supported_file_types if self.preferences else [],
            'max_concurrent_downloads': self.preferences.max_concurrent_downloads if self.preferences else 0,
            'last_loaded': self._last_loaded.isoformat() if self._last_loaded else None
        }


async def main():
    """Test the CourseManager functionality"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    logging.basicConfig(level=logging.INFO)
    
    manager = CourseManager()
    
    # Load configuration
    if await manager.load_configuration():
        print("Configuration loaded successfully!")
        
        # Print summary
        summary = manager.get_configuration_summary()
        print(f"Summary: {summary}")
        
        # Print enabled courses
        enabled = manager.get_enabled_courses()
        print(f"\nEnabled courses ({len(enabled)}):")
        for course in enabled:
            print(f"  - {course.name} (ID: {course.course_id}, Priority: {course.priority})")
    else:
        print("Failed to load configuration")


if __name__ == "__main__":
    asyncio.run(main())