#!/usr/bin/env python3
"""
State Manager - Processing state tracking and management

Handles tracking of what content has been processed, when it was processed,
and the status of processing operations for efficient incremental syncing.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json

from content_fingerprint import FingerprintGenerator, ContentFingerprint


class ProcessingStatus(Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProcessingState:
    """Processing state record"""
    entity_type: str  # 'course', 'module', 'file', 'page'
    entity_id: str
    fingerprint: str
    status: ProcessingStatus
    last_processed_at: Optional[datetime] = None
    created_at: datetime = None
    metadata: Dict[str, Any] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class StateManager:
    """Manages processing state and deduplication"""
    
    def __init__(self, storage_backend=None):
        self.logger = logging.getLogger(__name__)
        self.fingerprint_generator = FingerprintGenerator()
        self.storage_backend = storage_backend  # Database connection
        
        # In-memory cache for performance
        self._state_cache: Dict[str, ProcessingState] = {}
        self._cache_max_age = timedelta(minutes=30)
        self._last_cache_clear = datetime.now()
    
    def _get_cache_key(self, entity_type: str, entity_id: str) -> str:
        """Generate cache key for state record"""
        return f"{entity_type}:{entity_id}"
    
    def _clear_expired_cache(self):
        """Clear expired cache entries"""
        if datetime.now() - self._last_cache_clear > self._cache_max_age:
            self._state_cache.clear()
            self._last_cache_clear = datetime.now()
            self.logger.debug("Cleared state cache")
    
    async def should_process_entity(self, 
                                  entity_type: str, 
                                  entity_id: str, 
                                  current_fingerprint: str) -> bool:
        """
        Check if an entity should be processed based on fingerprint
        
        Args:
            entity_type: Type of entity ('course', 'module', 'file', 'page')
            entity_id: Canvas entity ID
            current_fingerprint: Current fingerprint of the entity
            
        Returns:
            True if entity should be processed, False if already processed
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(entity_type, entity_id)
            if cache_key in self._state_cache:
                cached_state = self._state_cache[cache_key]
                if cached_state.fingerprint == current_fingerprint and cached_state.status == ProcessingStatus.COMPLETED:
                    self.logger.debug(f"Cache hit: {entity_type} {entity_id} already processed")
                    return False
            
            # Check database
            existing_state = await self._get_processing_state(entity_type, entity_id)
            
            if existing_state:
                # Update cache
                self._state_cache[cache_key] = existing_state
                
                # If fingerprints match and processing completed, skip
                if (existing_state.fingerprint == current_fingerprint and 
                    existing_state.status == ProcessingStatus.COMPLETED):
                    self.logger.debug(f"Entity {entity_type}:{entity_id} already processed with same fingerprint")
                    return False
                
                # If fingerprint changed, should reprocess
                if existing_state.fingerprint != current_fingerprint:
                    self.logger.info(f"Entity {entity_type}:{entity_id} fingerprint changed, will reprocess")
                    return True
                
                # If processing failed, should retry (with limits)
                if existing_state.status == ProcessingStatus.FAILED:
                    if existing_state.retry_count < 3:  # Max 3 retries
                        self.logger.info(f"Retrying failed entity {entity_type}:{entity_id} (attempt {existing_state.retry_count + 1})")
                        return True
                    else:
                        self.logger.warning(f"Entity {entity_type}:{entity_id} exceeded max retries, skipping")
                        return False
                
                # If currently processing, skip (unless stuck for too long)
                if existing_state.status == ProcessingStatus.PROCESSING:
                    time_since_started = datetime.now() - existing_state.last_processed_at
                    if time_since_started > timedelta(hours=1):  # Stuck for > 1 hour
                        self.logger.warning(f"Entity {entity_type}:{entity_id} stuck in processing, will retry")
                        return True
                    else:
                        self.logger.debug(f"Entity {entity_type}:{entity_id} currently being processed")
                        return False
            
            # No existing state, should process
            self.logger.debug(f"New entity {entity_type}:{entity_id}, will process")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking processing state for {entity_type}:{entity_id}: {e}")
            # Default to processing on error
            return True
    
    async def mark_processing_started(self, 
                                    entity_type: str, 
                                    entity_id: str, 
                                    fingerprint: str,
                                    metadata: Dict[str, Any] = None) -> bool:
        """
        Mark an entity as currently being processed
        
        Args:
            entity_type: Type of entity
            entity_id: Canvas entity ID  
            fingerprint: Current fingerprint
            metadata: Additional metadata
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            state = ProcessingState(
                entity_type=entity_type,
                entity_id=entity_id,
                fingerprint=fingerprint,
                status=ProcessingStatus.PROCESSING,
                last_processed_at=datetime.now(),
                metadata=metadata or {}
            )
            
            await self._save_processing_state(state)
            
            # Update cache
            cache_key = self._get_cache_key(entity_type, entity_id)
            self._state_cache[cache_key] = state
            
            self.logger.debug(f"Marked {entity_type}:{entity_id} as processing")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark processing started for {entity_type}:{entity_id}: {e}")
            return False
    
    async def mark_processing_completed(self, 
                                      entity_type: str, 
                                      entity_id: str, 
                                      fingerprint: str,
                                      metadata: Dict[str, Any] = None) -> bool:
        """
        Mark an entity as successfully processed
        
        Args:
            entity_type: Type of entity
            entity_id: Canvas entity ID
            fingerprint: Current fingerprint
            metadata: Additional metadata
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            # Get existing state to preserve creation time and retry count
            existing_state = await self._get_processing_state(entity_type, entity_id)
            
            state = ProcessingState(
                entity_type=entity_type,
                entity_id=entity_id,
                fingerprint=fingerprint,
                status=ProcessingStatus.COMPLETED,
                last_processed_at=datetime.now(),
                created_at=existing_state.created_at if existing_state else datetime.now(),
                metadata=metadata or {},
                retry_count=existing_state.retry_count if existing_state else 0
            )
            
            await self._save_processing_state(state)
            
            # Update cache
            cache_key = self._get_cache_key(entity_type, entity_id)
            self._state_cache[cache_key] = state
            
            self.logger.debug(f"Marked {entity_type}:{entity_id} as completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark processing completed for {entity_type}:{entity_id}: {e}")
            return False
    
    async def mark_processing_failed(self, 
                                   entity_type: str, 
                                   entity_id: str, 
                                   fingerprint: str,
                                   error_message: str,
                                   metadata: Dict[str, Any] = None) -> bool:
        """
        Mark an entity as failed processing
        
        Args:
            entity_type: Type of entity
            entity_id: Canvas entity ID
            fingerprint: Current fingerprint
            error_message: Error description
            metadata: Additional metadata
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            # Get existing state to increment retry count
            existing_state = await self._get_processing_state(entity_type, entity_id)
            retry_count = (existing_state.retry_count if existing_state else 0) + 1
            
            state = ProcessingState(
                entity_type=entity_type,
                entity_id=entity_id,
                fingerprint=fingerprint,
                status=ProcessingStatus.FAILED,
                last_processed_at=datetime.now(),
                created_at=existing_state.created_at if existing_state else datetime.now(),
                metadata=metadata or {},
                error_message=error_message,
                retry_count=retry_count
            )
            
            await self._save_processing_state(state)
            
            # Update cache
            cache_key = self._get_cache_key(entity_type, entity_id)
            self._state_cache[cache_key] = state
            
            self.logger.warning(f"Marked {entity_type}:{entity_id} as failed (attempt {retry_count}): {error_message}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark processing failed for {entity_type}:{entity_id}: {e}")
            return False
    
    async def get_failed_entities(self, max_retries: int = 3) -> List[ProcessingState]:
        """
        Get entities that failed processing and are eligible for retry
        
        Args:
            max_retries: Maximum number of retries allowed
            
        Returns:
            List of failed entities eligible for retry
        """
        try:
            if self.storage_backend:
                # Implementation would query database for failed entities
                # This is a placeholder for the database query
                return []
            else:
                # In-memory fallback
                failed_entities = []
                for state in self._state_cache.values():
                    if (state.status == ProcessingStatus.FAILED and 
                        state.retry_count < max_retries):
                        failed_entities.append(state)
                return failed_entities
                
        except Exception as e:
            self.logger.error(f"Failed to get failed entities: {e}")
            return []
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            stats = {
                'total_entities': 0,
                'completed': 0,
                'failed': 0,
                'processing': 0,
                'pending': 0,
                'by_type': {}
            }
            
            if self.storage_backend:
                # Implementation would query database for statistics
                # This is a placeholder
                pass
            else:
                # In-memory statistics
                for state in self._state_cache.values():
                    stats['total_entities'] += 1
                    stats[state.status.value] = stats.get(state.status.value, 0) + 1
                    
                    entity_type = state.entity_type
                    if entity_type not in stats['by_type']:
                        stats['by_type'][entity_type] = {'total': 0, 'completed': 0, 'failed': 0}
                    
                    stats['by_type'][entity_type]['total'] += 1
                    if state.status == ProcessingStatus.COMPLETED:
                        stats['by_type'][entity_type]['completed'] += 1
                    elif state.status == ProcessingStatus.FAILED:
                        stats['by_type'][entity_type]['failed'] += 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get processing statistics: {e}")
            return {}
    
    async def cleanup_old_states(self, days_old: int = 30) -> int:
        """
        Clean up old processing states
        
        Args:
            days_old: Remove states older than this many days
            
        Returns:
            Number of states cleaned up
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            if self.storage_backend:
                # Implementation would delete old records from database
                # This is a placeholder
                return 0
            else:
                # In-memory cleanup
                to_remove = []
                for key, state in self._state_cache.items():
                    if state.created_at < cutoff_date:
                        to_remove.append(key)
                
                for key in to_remove:
                    del self._state_cache[key]
                
                self.logger.info(f"Cleaned up {len(to_remove)} old processing states")
                return len(to_remove)
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old states: {e}")
            return 0
    
    # Database interaction methods (placeholders for actual implementation)
    async def _get_processing_state(self, entity_type: str, entity_id: str) -> Optional[ProcessingState]:
        """Get processing state from storage backend"""
        # This would query the database in actual implementation
        # For now, return None (no existing state)
        return None
    
    async def _save_processing_state(self, state: ProcessingState) -> bool:
        """Save processing state to storage backend"""
        # This would save to database in actual implementation
        # For now, just log the action
        self.logger.debug(f"Would save state: {state.entity_type}:{state.entity_id} -> {state.status.value}")
        return True


async def main():
    """Test state manager functionality"""
    logging.basicConfig(level=logging.INFO)
    
    manager = StateManager()
    
    # Test fingerprint generation and state checking
    fingerprint_gen = FingerprintGenerator()
    
    file_info = {
        'id': 12345,
        'size': 1024768,
        'updated_at': '2024-01-15T10:30:00Z',
        'content-type': 'application/pdf',
        'display_name': 'lecture_notes.pdf'
    }
    
    fingerprint = fingerprint_gen.generate_file_fingerprint(file_info)
    
    # Test processing workflow
    entity_type = "file"
    entity_id = "12345"
    
    # Check if should process
    should_process = await manager.should_process_entity(entity_type, entity_id, fingerprint)
    print(f"Should process: {should_process}")
    
    # Mark as processing
    await manager.mark_processing_started(entity_type, entity_id, fingerprint, {'filename': 'test.pdf'})
    
    # Simulate processing completion
    await asyncio.sleep(1)
    await manager.mark_processing_completed(entity_type, entity_id, fingerprint, {'processed_chunks': 5})
    
    # Check again (should not process)
    should_process_again = await manager.should_process_entity(entity_type, entity_id, fingerprint)
    print(f"Should process again: {should_process_again}")
    
    # Get statistics
    stats = await manager.get_processing_statistics()
    print(f"Statistics: {stats}")


if __name__ == "__main__":
    asyncio.run(main())