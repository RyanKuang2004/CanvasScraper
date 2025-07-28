#!/usr/bin/env python3
"""
Supabase Client

Handles all Supabase interactions for storing and retrieving Canvas content,
chunks, and metadata with real-time capabilities.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json

from .text_chunker import TextChunk
from .file_processor_manager import ProcessingResponse

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class SupabaseClient:
    """Client for Supabase database operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client: Optional[Client] = None
        
        if not SUPABASE_AVAILABLE:
            self.logger.error("Supabase library not available - install with: pip install supabase")
            return
        
        # Initialize Supabase client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client with environment variables"""
        url = os.getenv('SUPABASE_URL')
        anon_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not url or not anon_key:
            self.logger.error("Supabase credentials not found - set SUPABASE_URL and SUPABASE_ANON_KEY")
            return
        
        try:
            self.client = create_client(url, anon_key)
            self.logger.info("Supabase client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Supabase client: {e}")
    
    def is_available(self) -> bool:
        """Check if Supabase client is available"""
        return self.client is not None
    
    async def store_course(self, course_data: Dict[str, Any]) -> Optional[str]:
        """Store course information"""
        if not self.is_available():
            return None
        
        try:
            # Prepare course data
            course_record = {
                'canvas_id': str(course_data.get('id')),
                'name': course_data.get('name'),
                'code': course_data.get('course_code'),
                'term': course_data.get('term', {}).get('name'),
                'start_date': course_data.get('start_at'),
                'end_date': course_data.get('end_at'),
                'enrollment_term_id': course_data.get('enrollment_term_id'),
                'workflow_state': course_data.get('workflow_state'),
                'course_format': course_data.get('course_format'),
                'is_public': course_data.get('is_public', False),
                'is_public_to_auth_users': course_data.get('is_public_to_auth_users', False),
                'public_syllabus': course_data.get('public_syllabus', False),
                'public_syllabus_to_auth': course_data.get('public_syllabus_to_auth', False),
                'public_description': course_data.get('public_description'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Insert or update course
            result = self.client.table('courses').upsert(
                course_record,
                on_conflict='canvas_id'
            ).execute()
            
            self.logger.info(f"Stored course: {course_data.get('name')}")
            return course_record['canvas_id']
            
        except Exception as e:
            self.logger.error(f"Failed to store course {course_data.get('name')}: {e}")
            return None
    
    async def store_module(self, module_data: Dict[str, Any], course_id: str) -> Optional[str]:
        """Store module information"""
        if not self.is_available():
            return None
        
        try:
            module_record = {
                'canvas_id': str(module_data.get('id')),
                'course_canvas_id': course_id,
                'name': module_data.get('name'),
                'position': module_data.get('position'),
                'unlock_at': module_data.get('unlock_at'),
                'require_sequential_progress': module_data.get('require_sequential_progress', False),
                'prerequisite_module_ids': json.dumps(module_data.get('prerequisite_module_ids', [])),
                'state': module_data.get('state'),
                'completed_at': module_data.get('completed_at'),
                'items_count': module_data.get('items_count', 0),
                'items_url': module_data.get('items_url'),
                'published': module_data.get('published', False),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('modules').upsert(
                module_record,
                on_conflict='canvas_id'
            ).execute()
            
            self.logger.info(f"Stored module: {module_data.get('name')}")
            return module_record['canvas_id']
            
        except Exception as e:
            self.logger.error(f"Failed to store module {module_data.get('name')}: {e}")
            return None
    
    async def store_file_content(self, processing_response: ProcessingResponse) -> Optional[str]:
        """Store file content and metadata"""
        if not self.is_available():
            return None
        
        try:
            # Store file record
            file_record = {
                'canvas_id': processing_response.file_id,
                'file_path': str(processing_response.file_path),
                'content_fingerprint': processing_response.fingerprint,
                'file_size': processing_response.processing_result.metadata.file_size if processing_response.processing_result else 0,
                'content_type': processing_response.processing_result.metadata.content_type if processing_response.processing_result else 'unknown',
                'extraction_method': processing_response.processing_result.metadata.extraction_method if processing_response.processing_result else 'unknown',
                'processing_time_ms': processing_response.processing_time_ms,
                'chunk_count': len(processing_response.chunks),
                'success': processing_response.success,
                'was_cached': processing_response.was_cached,
                'error_message': processing_response.error_message,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Add processing metadata if available
            if processing_response.processing_result:
                metadata = processing_response.processing_result.metadata
                file_record.update({
                    'page_count': metadata.page_count,
                    'word_count': metadata.word_count,
                    'character_count': metadata.character_count,
                    'language': metadata.language,
                    'author': metadata.author,
                    'title': metadata.title,
                    'subject': metadata.subject,
                    'creation_date': metadata.creation_date.isoformat() if metadata.creation_date else None,
                    'keywords': json.dumps(metadata.keywords) if metadata.keywords else None,
                    'has_images': metadata.has_images,
                    'has_tables': metadata.has_tables,
                    'errors': json.dumps(metadata.errors) if metadata.errors else None,
                    'warnings': json.dumps(metadata.warnings) if metadata.warnings else None
                })
            
            # Store file content
            file_result = self.client.table('file_contents').upsert(
                file_record,
                on_conflict='canvas_id'
            ).execute()
            
            if processing_response.processing_result and processing_response.processing_result.text_content:
                # Store full text content
                content_record = {
                    'file_canvas_id': processing_response.file_id,
                    'full_text': processing_response.processing_result.text_content,
                    'content_hash': processing_response.processing_result.content_hash,
                    'structured_content': json.dumps(processing_response.processing_result.structured_content) if processing_response.processing_result.structured_content else None,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                content_result = self.client.table('content_texts').upsert(
                    content_record,
                    on_conflict='file_canvas_id'
                ).execute()
            
            self.logger.info(f"Stored file content: {processing_response.file_path}")
            return processing_response.file_id
            
        except Exception as e:
            self.logger.error(f"Failed to store file content {processing_response.file_path}: {e}")
            return None
    
    async def store_chunks(self, chunks: List[TextChunk], file_id: str) -> int:
        """Store text chunks"""
        if not self.is_available() or not chunks:
            return 0
        
        try:
            chunk_records = []
            
            for chunk in chunks:
                chunk_record = {
                    'chunk_id': chunk.chunk_id,
                    'file_canvas_id': file_id,
                    'source_file_id': chunk.source_file_id,
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'content_hash': chunk.content_hash,
                    'char_start': chunk.char_start,
                    'char_end': chunk.char_end,
                    'token_count': chunk.token_count,
                    'section_title': chunk.section_title,
                    'page_number': chunk.page_number,
                    'slide_number': chunk.slide_number,
                    'heading_level': chunk.heading_level,
                    'metadata': json.dumps(chunk.metadata) if chunk.metadata else None,
                    'created_at': datetime.utcnow().isoformat()
                }
                chunk_records.append(chunk_record)
            
            # Batch insert chunks
            result = self.client.table('content_chunks').upsert(
                chunk_records,
                on_conflict='chunk_id'
            ).execute()
            
            self.logger.info(f"Stored {len(chunks)} chunks for file {file_id}")
            return len(chunks)
            
        except Exception as e:
            self.logger.error(f"Failed to store chunks for file {file_id}: {e}")
            return 0
    
    async def store_processing_response(self, response: ProcessingResponse) -> bool:
        """Store complete processing response (file + chunks)"""
        if not self.is_available():
            return False
        
        try:
            # Store file content first
            file_id = await self.store_file_content(response)
            if not file_id:
                return False
            
            # Store chunks
            chunks_stored = await self.store_chunks(response.chunks, file_id)
            
            success = file_id is not None and chunks_stored == len(response.chunks)
            self.logger.info(f"Stored processing response for {response.file_path}: {success}")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to store processing response: {e}")
            return False
    
    async def get_file_content(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve file content by ID"""
        if not self.is_available():
            return None
        
        try:
            result = self.client.table('file_contents').select('*').eq('canvas_id', file_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve file content {file_id}: {e}")
            return None
    
    async def get_chunks_for_file(self, file_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a file"""
        if not self.is_available():
            return []
        
        try:
            result = self.client.table('content_chunks').select('*').eq('file_canvas_id', file_id).order('chunk_index').execute()
            
            return result.data
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve chunks for file {file_id}: {e}")
            return []
    
    async def search_content(self, query: str, course_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search content using full-text search"""
        if not self.is_available():
            return []
        
        try:
            # Build query
            query_builder = self.client.table('content_chunks').select('''
                chunk_id,
                content,
                section_title,
                page_number,
                slide_number,
                token_count,
                file_canvas_id,
                file_contents!inner(
                    file_path,
                    content_type,
                    title,
                    author
                )
            ''')
            
            # Add full-text search
            query_builder = query_builder.text_search('content', f"'{query}'")
            
            # Filter by course if specified
            if course_id:
                query_builder = query_builder.contains('metadata', {'course_id': course_id})
            
            # Limit results
            query_builder = query_builder.limit(limit)
            
            result = query_builder.execute()
            
            self.logger.info(f"Found {len(result.data)} search results for query: {query}")
            return result.data
            
        except Exception as e:
            self.logger.error(f"Failed to search content: {e}")
            return []
    
    async def get_course_statistics(self, course_id: str) -> Dict[str, Any]:
        """Get statistics for a course"""
        if not self.is_available():
            return {}
        
        try:
            # Get course info
            course_result = self.client.table('courses').select('*').eq('canvas_id', course_id).execute()
            
            # Get file count
            files_result = self.client.table('file_contents').select('canvas_id', count='exact').contains('metadata', {'course_id': course_id}).execute()
            
            # Get chunk count
            chunks_result = self.client.table('content_chunks').select('chunk_id', count='exact').contains('metadata', {'course_id': course_id}).execute()
            
            # Get total text length
            text_result = self.client.table('content_chunks').select('token_count').contains('metadata', {'course_id': course_id}).execute()
            
            total_tokens = sum(chunk.get('token_count', 0) for chunk in text_result.data)
            
            stats = {
                'course_name': course_result.data[0].get('name') if course_result.data else 'Unknown',
                'file_count': files_result.count or 0,
                'chunk_count': chunks_result.count or 0,
                'total_tokens': total_tokens,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get course statistics: {e}")
            return {}
    
    async def cleanup_old_content(self, days_old: int = 90) -> int:
        """Clean up old content"""
        if not self.is_available():
            return 0
        
        try:
            cutoff_date = datetime.utcnow().replace(day=datetime.utcnow().day - days_old)
            
            # Delete old chunks first (due to foreign key constraints)
            chunks_result = self.client.table('content_chunks').delete().lt('created_at', cutoff_date.isoformat()).execute()
            
            # Delete old file contents
            files_result = self.client.table('file_contents').delete().lt('created_at', cutoff_date.isoformat()).execute()
            
            deleted_count = len(chunks_result.data) + len(files_result.data)
            self.logger.info(f"Cleaned up {deleted_count} old records")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old content: {e}")
            return 0


# Global client instance
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get global Supabase client instance"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client


async def main():
    """Test Supabase client"""
    logging.basicConfig(level=logging.INFO)
    
    client = get_supabase_client()
    
    if not client.is_available():
        print("Supabase client not available - check credentials")
        return
    
    # Test basic functionality
    stats = await client.get_course_statistics("test_course")
    print(f"Test statistics: {stats}")
    
    # Test search
    results = await client.search_content("machine learning", limit=5)
    print(f"Search results: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())