#!/usr/bin/env python3
"""
Assessment Processor

Dedicated processor for Canvas assignments and quizzes with unified handling,
content fingerprinting, and intelligent text chunking.
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from bs4 import BeautifulSoup

from content_fingerprint import ContentFingerprint
from supabase_client import get_supabase_client
from text_chunker import TextChunker


class AssessmentProcessingError(Exception):
    """Exception raised during assessment processing"""
    pass


class AssessmentProcessor:
    """Processes Canvas assignments and quizzes with unified handling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supabase = get_supabase_client()
        self.fingerprint_generator = ContentFingerprint()
        self.text_chunker = TextChunker()
        
        # Processing statistics
        self.stats = {
            'assessments_processed': 0,
            'chunks_created': 0,
            'duplicates_skipped': 0,
            'errors': []
        }
        
        self.logger.info("Assessment Processor initialized")
    
    async def process_course_assessments(self, course_id: str, assignments: List[Dict], quizzes: List[Dict], force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Process all assignments and quizzes for a course
        
        Args:
            course_id: Canvas course ID
            assignments: List of assignment data from Canvas API
            quizzes: List of quiz data from Canvas API  
            force_reprocess: Force reprocessing even if fingerprint matches
            
        Returns:
            Processing statistics and results
        """
        self.logger.info(f"Processing {len(assignments)} assignments and {len(quizzes)} quizzes for course {course_id}")
        
        results = {
            'course_id': course_id,
            'assignments_processed': 0,
            'quizzes_processed': 0,
            'total_chunks_created': 0,
            'duplicates_skipped': 0,
            'errors': []
        }
        
        try:
            # Process assignments
            for assignment in assignments:
                try:
                    result = await self.process_single_assessment(assignment, 'assignment', course_id, force_reprocess)
                    if result['status'] == 'processed':
                        results['assignments_processed'] += 1
                        results['total_chunks_created'] += result['chunks_created']
                    elif result['status'] == 'skipped':
                        results['duplicates_skipped'] += 1
                except Exception as e:
                    error_msg = f"Failed to process assignment {assignment.get('id', 'unknown')}: {str(e)}"
                    self.logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Process quizzes
            for quiz in quizzes:
                try:
                    result = await self.process_single_assessment(quiz, 'quiz', course_id, force_reprocess)
                    if result['status'] == 'processed':
                        results['quizzes_processed'] += 1
                        results['total_chunks_created'] += result['chunks_created']
                    elif result['status'] == 'skipped':
                        results['duplicates_skipped'] += 1
                except Exception as e:
                    error_msg = f"Failed to process quiz {quiz.get('id', 'unknown')}: {str(e)}"
                    self.logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            self.logger.info(f"Course {course_id} processing completed: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Failed to process assessments for course {course_id}: {str(e)}"
            self.logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    async def process_single_assessment(self, assessment_data: Dict, assessment_type: str, course_id: str, force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Process a single assignment or quiz
        
        Args:
            assessment_data: Raw assessment data from Canvas API
            assessment_type: 'assignment' or 'quiz'
            course_id: Canvas course ID
            force_reprocess: Force reprocessing even if fingerprint matches
            
        Returns:
            Processing result with status and metadata
        """
        assessment_id = assessment_data.get('id')
        assessment_name = assessment_data.get('name') or assessment_data.get('title', 'Unnamed Assessment')
        
        self.logger.debug(f"Processing {assessment_type} {assessment_id}: {assessment_name}")
        
        try:
            # Extract and clean content
            content_data = self._extract_content(assessment_data, assessment_type)
            
            # Generate content fingerprint
            fingerprint = self.fingerprint_generator.generate_from_text(content_data['combined_text'])
            
            # Check if reprocessing is needed
            if not force_reprocess and not await self._needs_processing(assessment_id, fingerprint):
                self.logger.debug(f"Skipping {assessment_type} {assessment_id} - already processed")
                return {
                    'status': 'skipped',
                    'reason': 'already_processed',
                    'assessment_id': assessment_id,
                    'fingerprint': fingerprint
                }
            
            # Store assessment metadata
            assessment_record = await self._store_assessment_metadata(
                assessment_data, assessment_type, course_id, fingerprint, content_data
            )
            
            # Process and chunk content
            chunks = []
            if content_data['combined_text'].strip():
                chunks = await self._process_and_chunk_content(
                    content_data, assessment_id, course_id
                )
            
            # Update processing status
            await self._update_processing_status(assessment_id, len(chunks))
            
            self.logger.info(f"Successfully processed {assessment_type} {assessment_id}: {len(chunks)} chunks created")
            
            return {
                'status': 'processed',
                'assessment_id': assessment_id,
                'assessment_type': assessment_type,
                'chunks_created': len(chunks),
                'fingerprint': fingerprint,
                'content_length': len(content_data['combined_text'])
            }
            
        except Exception as e:
            error_msg = f"Failed to process {assessment_type} {assessment_id}: {str(e)}"
            self.logger.error(error_msg)
            raise AssessmentProcessingError(error_msg) from e
    
    def _extract_content(self, assessment_data: Dict, assessment_type: str) -> Dict[str, str]:
        """
        Extract and clean content from assessment data
        
        Args:
            assessment_data: Raw assessment data from Canvas API
            assessment_type: 'assignment' or 'quiz'
            
        Returns:
            Dictionary with cleaned content sections
        """
        content = {
            'name': assessment_data.get('name') or assessment_data.get('title', ''),
            'description_html': '',
            'description_text': '',
            'instructions': '',
            'combined_text': ''
        }
        
        # Extract description (assignments) or description (quizzes)
        description_html = assessment_data.get('description', '')
        if description_html:
            content['description_html'] = description_html
            content['description_text'] = self._html_to_text(description_html)
            content['instructions'] = content['description_text']  # For search purposes
        
        # Combine all text content for fingerprinting and chunking
        text_parts = [
            content['name'],
            content['description_text']
        ]
        
        # Add type-specific content
        if assessment_type == 'assignment':
            # Add submission instructions if available
            if 'submission_types' in assessment_data:
                submission_info = f"Submission types: {', '.join(assessment_data['submission_types'])}"
                text_parts.append(submission_info)
        
        content['combined_text'] = '\n\n'.join(filter(None, text_parts))
        
        return content
    
    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to clean plain text
        
        Args:
            html_content: HTML string to convert
            
        Returns:
            Clean plain text string
        """
        if not html_content:
            return ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Get text and clean up whitespace
            text = soup.get_text(separator=' ', strip=True)
            return ' '.join(text.split())  # Normalize whitespace
        except Exception as e:
            self.logger.warning(f"Error converting HTML to text: {e}")
            return html_content  # Return raw HTML as fallback
    
    async def _needs_processing(self, assessment_id: int, fingerprint: str) -> bool:
        """
        Check if assessment needs processing based on fingerprint
        
        Args:
            assessment_id: Canvas assessment ID
            fingerprint: Content fingerprint
            
        Returns:
            True if processing is needed
        """
        try:
            if not self.supabase.is_available():
                return True  # Always process if Supabase not available
            
            result = await self.supabase.client.table('course_assessments').select('content_fingerprint').eq('id', assessment_id).single().execute()
            
            if result.data:
                existing_fingerprint = result.data.get('content_fingerprint')
                return existing_fingerprint != fingerprint
            
            return True  # New assessment, needs processing
            
        except Exception as e:
            self.logger.warning(f"Error checking processing status for assessment {assessment_id}: {e}")
            return True  # Process if unsure
    
    async def _store_assessment_metadata(self, assessment_data: Dict, assessment_type: str, course_id: str, fingerprint: str, content_data: Dict) -> Dict:
        """
        Store assessment metadata in Supabase
        
        Args:
            assessment_data: Raw assessment data from Canvas API
            assessment_type: 'assignment' or 'quiz'
            course_id: Canvas course ID
            fingerprint: Content fingerprint
            content_data: Processed content data
            
        Returns:
            Stored assessment record
        """
        if not self.supabase.is_available():
            self.logger.warning("Supabase not available - skipping metadata storage")
            return {}
        
        # Base record structure
        record = {
            'id': assessment_data['id'],
            'course_id': int(course_id),
            'type': assessment_type,
            'name': content_data['name'],
            'description': content_data['description_text'],
            'description_html': content_data['description_html'],
            'instructions': content_data['instructions'],
            'due_at': assessment_data.get('due_at'),
            'unlock_at': assessment_data.get('unlock_at'),
            'lock_at': assessment_data.get('lock_at'),
            'workflow_state': assessment_data.get('workflow_state', 'published'),
            'published': assessment_data.get('published', True),
            'content_fingerprint': fingerprint,
            'content_processed': False,  # Will be updated after chunking
            'canvas_created_at': assessment_data.get('created_at'),
            'canvas_updated_at': assessment_data.get('updated_at'),
            'last_synced_at': datetime.utcnow().isoformat()
        }
        
        # Add type-specific fields
        if assessment_type == 'assignment':
            record.update({
                'points_possible': assessment_data.get('points_possible'),
                'grading_type': assessment_data.get('grading_type'),
                'submission_types': assessment_data.get('submission_types', []),
                'allowed_extensions': assessment_data.get('allowed_extensions', [])
            })
        elif assessment_type == 'quiz':
            record.update({
                'quiz_type': assessment_data.get('quiz_type'),
                'time_limit': assessment_data.get('time_limit'),
                'allowed_attempts': assessment_data.get('allowed_attempts'),
                'shuffle_answers': assessment_data.get('shuffle_answers', False),
                'show_correct_answers': assessment_data.get('show_correct_answers', True),
                'show_correct_answers_at': assessment_data.get('show_correct_answers_at')
            })
        
        try:
            result = await self.supabase.client.table('course_assessments').upsert(record).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.debug(f"Stored {assessment_type} metadata for {assessment_data['id']}")
                return result.data[0]
            else:
                self.logger.warning(f"No data returned when storing {assessment_type} {assessment_data['id']}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Failed to store {assessment_type} metadata: {e}")
            raise AssessmentProcessingError(f"Database storage failed: {e}") from e
    
    async def _process_and_chunk_content(self, content_data: Dict, assessment_id: int, course_id: str) -> List[Dict]:
        """
        Process and chunk assessment content
        
        Args:
            content_data: Processed content data
            assessment_id: Canvas assessment ID
            course_id: Canvas course ID
            
        Returns:
            List of created chunk records
        """
        if not content_data['combined_text'].strip():
            return []
        
        try:
            # Generate text chunks
            chunks = self.text_chunker.chunk_text(
                content_data['combined_text'],
                metadata={
                    'assessment_id': assessment_id,
                    'course_id': course_id,
                    'source_type': 'assessment_content'
                }
            )
            
            # Store chunks in Supabase
            chunk_records = []
            for i, chunk in enumerate(chunks):
                chunk_record = await self._store_content_chunk(
                    chunk, assessment_id, course_id, i
                )
                if chunk_record:
                    chunk_records.append(chunk_record)
            
            self.logger.debug(f"Created {len(chunk_records)} chunks for assessment {assessment_id}")
            return chunk_records
            
        except Exception as e:
            self.logger.error(f"Failed to process and chunk content for assessment {assessment_id}: {e}")
            raise AssessmentProcessingError(f"Content chunking failed: {e}") from e
    
    async def _store_content_chunk(self, chunk: Dict, assessment_id: int, course_id: str, chunk_index: int) -> Optional[Dict]:
        """
        Store a single content chunk in Supabase
        
        Args:
            chunk: Text chunk data
            assessment_id: Canvas assessment ID
            course_id: Canvas course ID
            chunk_index: Index of chunk within assessment
            
        Returns:
            Stored chunk record or None if failed
        """
        if not self.supabase.is_available():
            return None
        
        # Generate chunk fingerprint
        chunk_fingerprint = hashlib.sha256(chunk['text'].encode()).hexdigest()
        
        chunk_record = {
            'assessment_id': assessment_id,
            'course_id': int(course_id),
            'chunk_text': chunk['text'],
            'chunk_index': chunk_index,
            'chunk_size': len(chunk['text']),
            'source_type': 'description',  # Could be extended for other sources
            'chunk_fingerprint': chunk_fingerprint
        }
        
        try:
            result = await self.supabase.client.table('assessment_content_chunks').insert(chunk_record).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                self.logger.warning(f"No data returned when storing chunk for assessment {assessment_id}")
                return None
                
        except Exception as e:
            # Handle unique constraint violations gracefully (duplicate chunks)
            if 'duplicate key value' in str(e).lower():
                self.logger.debug(f"Duplicate chunk skipped for assessment {assessment_id}")
                return None
            else:
                self.logger.error(f"Failed to store content chunk: {e}")
                return None
    
    async def _update_processing_status(self, assessment_id: int, chunks_count: int):
        """
        Update processing status for an assessment
        
        Args:
            assessment_id: Canvas assessment ID
            chunks_count: Number of chunks created
        """
        if not self.supabase.is_available():
            return
        
        update_data = {
            'content_processed': True,
            'content_chunks_count': chunks_count,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        try:
            await self.supabase.client.table('course_assessments').update(update_data).eq('id', assessment_id).execute()
            self.logger.debug(f"Updated processing status for assessment {assessment_id}")
        except Exception as e:
            self.logger.error(f"Failed to update processing status for assessment {assessment_id}: {e}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset processing statistics"""
        self.stats = {
            'assessments_processed': 0,
            'chunks_created': 0,
            'duplicates_skipped': 0,
            'errors': []
        }