#!/usr/bin/env python3
"""
Canvas Content Orchestrator

Main orchestrator that coordinates course selection, file processing,
deduplication, chunking, and Supabase storage.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from canvas_client import CanvasClient
from config import Config
from course_manager import CourseManager
from file_processor_manager import FileProcessorManager, ProcessingRequest
from scheduler import MelbourneScheduler
from supabase_client import get_supabase_client


class CanvasOrchestrator:
    """Main orchestrator for Canvas content processing"""
    
    def __init__(self, config_path: Path = None):
        self.logger = logging.getLogger(__name__)
        
        # Initialize configuration
        self.config = Config()
        
        # Initialize components
        self.course_manager = CourseManager(config_path)
        self.file_processor = FileProcessorManager()
        self.supabase = get_supabase_client()
        self.scheduler = MelbourneScheduler()
        self.canvas_client = CanvasClient()
        
        # Processing statistics
        self.stats = {
            'courses_processed': 0,
            'files_processed': 0,
            'chunks_created': 0,
            'processing_time_ms': 0,
            'last_run': None,
            'errors': []
        }
        
        self.logger.info("Canvas Orchestrator initialized")
    
    async def run_full_sync(self, force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Run complete synchronization of Canvas content
        
        Args:
            force_reprocess: Force reprocessing of all files
            
        Returns:
            Processing statistics and results
        """
        start_time = time.time()
        self.logger.info("Starting full Canvas content synchronization")
        
        try:
            # Reset statistics
            self.stats = {
                'courses_processed': 0,
                'files_processed': 0,
                'chunks_created': 0,
                'processing_time_ms': 0,
                'last_run': datetime.utcnow().isoformat(),
                'errors': []
            }
            
            # Load course configuration
            course_config = await self.course_manager.load_configuration()
            enabled_courses = await self.course_manager.get_enabled_courses()
            
            if not enabled_courses:
                self.logger.warning("No courses enabled for processing")
                return self.stats
            
            self.logger.info(f"Processing {len(enabled_courses)} enabled courses")
            
            # Process each enabled course
            for course_id in enabled_courses:
                await self._process_course(course_id, force_reprocess)
                self.stats['courses_processed'] += 1
            
            # Calculate total processing time
            self.stats['processing_time_ms'] = int((time.time() - start_time) * 1000)
            
            self.logger.info(f"Synchronization completed: {self.stats}")
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Full sync failed: {e}")
            self.stats['errors'].append(str(e))
            self.stats['processing_time_ms'] = int((time.time() - start_time) * 1000)
            return self.stats
    
    async def _process_course(self, course_id: str, force_reprocess: bool = False):
        """Process a single course"""
        try:
            self.logger.info(f"Processing course {course_id}")
            
            # Fetch course information from Canvas
            course_data = await self.canvas_client.get_course(course_id)
            if not course_data:
                self.logger.error(f"Failed to fetch course data for {course_id}")
                return
            
            # Store course in Supabase
            if self.supabase.is_available():
                await self.supabase.store_course(course_data)
            
            # Get course modules
            modules = await self.canvas_client.get_course_modules(course_id)
            if not modules:
                self.logger.warning(f"No modules found for course {course_id}")
                return
            
            # Process each module
            for module_data in modules:
                module_id = str(module_data.get('id'))
                
                # Check if module should be processed
                if not await self.course_manager.should_process_module(course_id, module_id):
                    self.logger.debug(f"Skipping module {module_id} (not enabled)")
                    continue
                
                # Store module in Supabase
                if self.supabase.is_available():
                    await self.supabase.store_module(module_data, course_id)
                
                # Process module items
                await self._process_module(course_id, module_data, force_reprocess)
                
        except Exception as e:
            self.logger.error(f"Failed to process course {course_id}: {e}")
            self.stats['errors'].append(f"Course {course_id}: {str(e)}")
    
    async def _process_module(self, course_id: str, module_data: Dict[str, Any], force_reprocess: bool = False):
        """Process a single module"""
        module_id = str(module_data.get('id'))
        module_name = module_data.get('name', 'Unknown Module')
        
        try:
            self.logger.info(f"Processing module {module_name} ({module_id})")
            
            # Get module items
            items = await self.canvas_client.get_module_items(course_id, module_id)
            if not items:
                self.logger.debug(f"No items found in module {module_id}")
                return
            
            # Filter for file items
            file_items = [
                item for item in items 
                if item.get('type') == 'File' and 
                await self.course_manager.should_process_file(course_id, item)
            ]
            
            if not file_items:
                self.logger.debug(f"No processable files in module {module_id}")
                return
            
            self.logger.info(f"Found {len(file_items)} files to process in module {module_name}")
            
            # Process files in batches
            processing_requests = []
            
            for item in file_items:
                file_id = str(item.get('content_id', item.get('id')))
                
                # Download file
                file_path = await self._download_file(course_id, file_id, item)
                if not file_path:
                    continue
                
                # Create processing request
                request = ProcessingRequest(
                    file_path=file_path,
                    source_id=file_id,
                    course_id=course_id,
                    module_id=module_id,
                    metadata={
                        'course_name': module_data.get('course_name', ''),
                        'module_name': module_name,
                        'item_title': item.get('title', ''),
                        'item_type': item.get('type', ''),
                        'canvas_url': item.get('html_url', ''),
                        'position': item.get('position', 0)
                    },
                    force_reprocess=force_reprocess
                )
                processing_requests.append(request)
            
            # Process files in parallel
            if processing_requests:
                responses = await self.file_processor.process_multiple_files(processing_requests)
                
                # Store results in Supabase
                for response in responses:
                    if response.success:
                        self.stats['files_processed'] += 1
                        self.stats['chunks_created'] += len(response.chunks)
                        
                        if self.supabase.is_available():
                            await self.supabase.store_processing_response(response)
                    else:
                        self.stats['errors'].append(f"File {response.file_path}: {response.error_message}")
                
        except Exception as e:
            self.logger.error(f"Failed to process module {module_id}: {e}")
            self.stats['errors'].append(f"Module {module_id}: {str(e)}")
    
    async def _download_file(self, course_id: str, file_id: str, item: Dict[str, Any]) -> Optional[Path]:
        """Download a file from Canvas"""
        try:
            # Get file information
            file_info = await self.canvas_client.get_file(file_id)
            if not file_info:
                self.logger.warning(f"Could not get file info for {file_id}")
                return None
            
            # Check if file type is supported
            filename = file_info.get('filename', f"file_{file_id}")
            file_path = self.file_processor.storage_dir / f"{course_id}_{file_id}_{filename}"
            
            if not self.file_processor.can_process_file(file_path):
                self.logger.debug(f"Skipping unsupported file type: {filename}")
                return None
            
            # Download file if not already exists
            if not file_path.exists():
                success = await self.canvas_client.download_file(file_info, file_path)
                if not success:
                    self.logger.error(f"Failed to download file {filename}")
                    return None
                
                self.logger.info(f"Downloaded file: {filename}")
            else:
                self.logger.debug(f"File already exists: {filename}")
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"Failed to download file {file_id}: {e}")
            return None
    
    async def search_content(self, query: str, course_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search content across all processed files"""
        if not self.supabase.is_available():
            self.logger.warning("Supabase not available - cannot search content")
            return []
        
        try:
            results = await self.supabase.search_content(query, course_id, limit)
            self.logger.info(f"Found {len(results)} search results for query: {query}")
            return results
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []
    
    async def get_course_statistics(self, course_id: Optional[str] = None) -> Dict[str, Any]:
        """Get processing statistics"""
        try:
            stats = {
                'orchestrator_stats': self.stats,
                'file_processor_stats': await self.file_processor.get_processing_statistics(),
                'course_manager_stats': await self.course_manager.get_statistics()
            }
            
            if self.supabase.is_available():
                if course_id:
                    stats['supabase_stats'] = await self.supabase.get_course_statistics(course_id)
                else:
                    # Get stats for all enabled courses
                    enabled_courses = await self.course_manager.get_enabled_courses()
                    course_stats = {}
                    for cid in enabled_courses[:5]:  # Limit to first 5 courses
                        course_stats[cid] = await self.supabase.get_course_statistics(cid)
                    stats['course_statistics'] = course_stats
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}
    
    async def cleanup_old_data(self, days_old: int = 30):
        """Clean up old processing data"""
        try:
            self.logger.info(f"Cleaning up data older than {days_old} days")
            
            # Cleanup file processor state
            await self.file_processor.cleanup_old_state(days_old)
            
            # Cleanup Supabase content
            if self.supabase.is_available():
                deleted_count = await self.supabase.cleanup_old_content(days_old)
                self.logger.info(f"Cleaned up {deleted_count} old records from Supabase")
                
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
    
    def start_scheduled_processing(self):
        """Start scheduled processing jobs"""
        try:
            # Schedule regular sync jobs
            self.scheduler.setup_scheduled_jobs(
                sync_callback=self.run_full_sync,
                cleanup_callback=self.cleanup_old_data
            )
            
            self.logger.info("Scheduled processing started")
            
        except Exception as e:
            self.logger.error(f"Failed to start scheduled processing: {e}")
    
    def stop_scheduled_processing(self):
        """Stop scheduled processing"""
        try:
            self.scheduler.shutdown()
            self.logger.info("Scheduled processing stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop scheduled processing: {e}")


async def main():
    """Test the orchestrator"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create orchestrator
    orchestrator = CanvasOrchestrator()
    
    # Check if Supabase is available
    if not orchestrator.supabase.is_available():
        print("Warning: Supabase not available - data will not be stored")
    
    # Load course configuration
    config = await orchestrator.course_manager.load_configuration()
    enabled_courses = await orchestrator.course_manager.get_enabled_courses()
    
    print(f"Configuration loaded: {len(enabled_courses)} courses enabled")
    
    # Run a test sync (limited scope)
    if enabled_courses:
        print("Running test synchronization...")
        stats = await orchestrator.run_full_sync()
        print(f"Sync completed: {stats}")
        
        # Test search if Supabase is available
        if orchestrator.supabase.is_available() and stats['chunks_created'] > 0:
            print("\nTesting search functionality...")
            search_results = await orchestrator.search_content("machine learning", limit=3)
            print(f"Search results: {len(search_results)}")
            
            for result in search_results[:2]:
                print(f"- {result.get('section_title', 'No title')}: {result.get('content', '')[:100]}...")
        
        # Get statistics
        print("\nGetting statistics...")
        all_stats = await orchestrator.get_course_statistics()
        print(f"Statistics: {all_stats}")
    
    else:
        print("No courses enabled for processing")


if __name__ == "__main__":
    asyncio.run(main())