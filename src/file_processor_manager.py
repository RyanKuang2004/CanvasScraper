#!/usr/bin/env python3
"""
File Processor Manager

Coordinates file processing with deduplication, chunking, and fingerprinting.
Integrates content fingerprinting to avoid reprocessing unchanged files.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import time

from content_fingerprint import FingerprintGenerator
from state_manager import StateManager
from text_chunker import SmartChunker, TextChunk
from file_processors.base_processor import BaseFileProcessor, ProcessingResult, FileProcessorFactory
from file_processors.pdf_processor import PDFProcessor
from file_processors.pptx_processor import PowerPointProcessor
from file_processors.docx_processor import WordProcessor


@dataclass
class ProcessingRequest:
    """Request for processing a file"""
    file_path: Path
    source_id: str  # Canvas file ID or similar
    course_id: str
    module_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    force_reprocess: bool = False


@dataclass
class ProcessingResponse:
    """Response from file processing"""
    success: bool
    file_id: str
    file_path: Path
    chunks: List[TextChunk]
    processing_result: Optional[ProcessingResult] = None
    fingerprint: Optional[str] = None
    was_cached: bool = False
    processing_time_ms: int = 0
    error_message: Optional[str] = None


class FileProcessorManager:
    """Manages file processing with deduplication and chunking"""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 overlap: int = 200,
                 storage_dir: Path = None):
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.fingerprint_generator = FingerprintGenerator()
        self.state_manager = StateManager()
        self.chunker = SmartChunker(
            chunk_size=chunk_size,
            overlap=overlap,
            preserve_structure=True
        )
        
        # Initialize file processor factory and register processors
        self.processor_factory = FileProcessorFactory()
        self._register_processors()
        
        # Storage directory for downloaded files
        self.storage_dir = storage_dir or Path("downloads")
        self.storage_dir.mkdir(exist_ok=True)
        
        self.logger.info("FileProcessorManager initialized")
    
    def _register_processors(self):
        """Register all available file processors"""
        # PDF processor
        self.processor_factory.register_processor(
            PDFProcessor,
            extensions=['.pdf'],
            mime_types=['application/pdf']
        )
        
        # PowerPoint processor
        self.processor_factory.register_processor(
            PowerPointProcessor,
            extensions=['.pptx'],
            mime_types=['application/vnd.openxmlformats-officedocument.presentationml.presentation']
        )
        
        # Word processor
        self.processor_factory.register_processor(
            WordProcessor,
            extensions=['.docx'],
            mime_types=['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        )
        
        self.logger.info("Registered file processors: PDF, PPTX, DOCX")
    
    async def process_file(self, request: ProcessingRequest) -> ProcessingResponse:
        """
        Process a file with deduplication and chunking
        
        Args:
            request: Processing request with file details
            
        Returns:
            ProcessingResponse with chunks and metadata
        """
        start_time = time.time()
        file_id = f"{request.course_id}_{request.source_id}"
        
        try:
            # Check if file exists
            if not request.file_path.exists():
                return ProcessingResponse(
                    success=False,
                    file_id=file_id,
                    file_path=request.file_path,
                    chunks=[],
                    error_message=f"File not found: {request.file_path}",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # Generate content fingerprint
            fingerprint = await self.fingerprint_generator.generate_file_fingerprint(request.file_path)
            
            # Check if we should process this file
            if not request.force_reprocess:
                if not await self.state_manager.should_process_entity(
                    entity_type="file",
                    entity_id=file_id,
                    fingerprint=fingerprint
                ):
                    self.logger.info(f"Skipping {request.file_path} - already processed with same fingerprint")
                    
                    # Try to return cached chunks if available
                    cached_chunks = await self._get_cached_chunks(file_id)
                    return ProcessingResponse(
                        success=True,
                        file_id=file_id,
                        file_path=request.file_path,
                        chunks=cached_chunks,
                        fingerprint=fingerprint,
                        was_cached=True,
                        processing_time_ms=int((time.time() - start_time) * 1000)
                    )
            
            # Mark processing as started
            await self.state_manager.mark_processing_started(
                entity_type="file",
                entity_id=file_id,
                fingerprint=fingerprint
            )
            
            # Get appropriate processor
            processor = self.processor_factory.get_processor(request.file_path)
            if not processor:
                error_msg = f"No processor available for file type: {request.file_path.suffix}"
                self.logger.error(error_msg)
                return ProcessingResponse(
                    success=False,
                    file_id=file_id,
                    file_path=request.file_path,
                    chunks=[],
                    error_message=error_msg,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # Extract text from file
            self.logger.info(f"Processing {request.file_path} with {processor.__class__.__name__}")
            processing_result = await processor.extract_text(request.file_path)
            
            if not processing_result.success:
                error_msg = f"Text extraction failed: {', '.join(processing_result.metadata.errors)}"
                self.logger.error(error_msg)
                return ProcessingResponse(
                    success=False,
                    file_id=file_id,
                    file_path=request.file_path,
                    chunks=[],
                    processing_result=processing_result,
                    fingerprint=fingerprint,
                    error_message=error_msg,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # Create chunks from extracted text
            chunks = await self._create_chunks(
                text=processing_result.text_content,
                file_id=file_id,
                request=request,
                processing_result=processing_result
            )
            
            # Mark processing as completed
            await self.state_manager.mark_processing_completed(
                entity_type="file",
                entity_id=file_id,
                fingerprint=fingerprint,
                metadata={
                    'chunk_count': len(chunks),
                    'character_count': processing_result.metadata.character_count,
                    'processing_method': processing_result.metadata.extraction_method
                }
            )
            
            self.logger.info(f"Successfully processed {request.file_path} -> {len(chunks)} chunks")
            
            return ProcessingResponse(
                success=True,
                file_id=file_id,
                file_path=request.file_path,
                chunks=chunks,
                processing_result=processing_result,
                fingerprint=fingerprint,
                was_cached=False,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to process {request.file_path}: {e}")
            return ProcessingResponse(
                success=False,
                file_id=file_id,
                file_path=request.file_path,
                chunks=[],
                fingerprint=fingerprint if 'fingerprint' in locals() else None,
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _create_chunks(self, 
                           text: str, 
                           file_id: str, 
                           request: ProcessingRequest,
                           processing_result: ProcessingResult) -> List[TextChunk]:
        """Create text chunks with enriched metadata"""
        if not text or len(text.strip()) < 50:
            self.logger.warning(f"Insufficient text content for chunking: {len(text)} characters")
            return []
        
        # Prepare metadata for chunking
        chunk_metadata = {
            'course_id': request.course_id,
            'module_id': request.module_id,
            'source_id': request.source_id,
            'file_path': str(request.file_path),
            'content_type': processing_result.metadata.content_type,
            'extraction_method': processing_result.metadata.extraction_method,
            'file_size': processing_result.metadata.file_size,
            'processing_time_ms': processing_result.metadata.processing_time_ms
        }
        
        # Add file-specific metadata
        if processing_result.metadata.author:
            chunk_metadata['author'] = processing_result.metadata.author
        if processing_result.metadata.title:
            chunk_metadata['document_title'] = processing_result.metadata.title
        if processing_result.metadata.subject:
            chunk_metadata['subject'] = processing_result.metadata.subject
        if processing_result.metadata.creation_date:
            chunk_metadata['creation_date'] = processing_result.metadata.creation_date.isoformat()
        if processing_result.metadata.keywords:
            chunk_metadata['keywords'] = processing_result.metadata.keywords
        
        # Add custom metadata from request
        if request.metadata:
            chunk_metadata.update(request.metadata)
        
        # Create chunks
        chunks = self.chunker.chunk_text(
            text=text,
            source_file_id=file_id,
            metadata=chunk_metadata
        )
        
        # Enrich chunks with additional processing information
        for chunk in chunks:
            chunk.metadata.update({
                'has_images': processing_result.metadata.has_images,
                'has_tables': processing_result.metadata.has_tables,
                'language': processing_result.metadata.language,
                'word_count_file': processing_result.metadata.word_count,
                'character_count_file': processing_result.metadata.character_count
            })
        
        return chunks
    
    async def _get_cached_chunks(self, file_id: str) -> List[TextChunk]:
        """Retrieve cached chunks for a file (placeholder implementation)"""
        # This would integrate with your storage system (Supabase, database, etc.)
        # For now, return empty list - will be implemented in Supabase integration
        return []
    
    async def process_multiple_files(self, requests: List[ProcessingRequest]) -> List[ProcessingResponse]:
        """Process multiple files concurrently"""
        self.logger.info(f"Processing {len(requests)} files concurrently")
        
        # Process files in batches to avoid overwhelming the system
        batch_size = 5
        all_responses = []
        
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            self.logger.info(f"Processing batch {i//batch_size + 1}: files {i+1}-{min(i+batch_size, len(requests))}")
            
            # Process batch concurrently
            tasks = [self.process_file(request) for request in batch]
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions
            for j, response in enumerate(batch_responses):
                if isinstance(response, Exception):
                    self.logger.error(f"Exception processing file {batch[j].file_path}: {response}")
                    error_response = ProcessingResponse(
                        success=False,
                        file_id=f"{batch[j].course_id}_{batch[j].source_id}",
                        file_path=batch[j].file_path,
                        chunks=[],
                        error_message=str(response)
                    )
                    all_responses.append(error_response)
                else:
                    all_responses.append(response)
        
        success_count = sum(1 for r in all_responses if r.success)
        self.logger.info(f"Completed processing: {success_count}/{len(requests)} files successful")
        
        return all_responses
    
    def can_process_file(self, file_path: Path) -> bool:
        """Check if a file can be processed"""
        processor = self.processor_factory.get_processor(file_path)
        return processor is not None
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        stats = await self.state_manager.get_statistics()
        
        # Add processor-specific stats
        stats.update({
            'supported_extensions': ['.pdf', '.pptx', '.docx'],
            'chunk_size': self.chunker.chunk_size,
            'chunk_overlap': self.chunker.overlap,
            'storage_directory': str(self.storage_dir)
        })
        
        return stats
    
    async def cleanup_old_state(self, days_old: int = 30):
        """Clean up old processing state"""
        await self.state_manager.cleanup_old_state(days_old)


async def main():
    """Test the file processor manager"""
    logging.basicConfig(level=logging.INFO)
    
    manager = FileProcessorManager()
    
    # Test with a sample file (you would need to provide a real file)
    test_file = Path("sample.pdf")
    if test_file.exists():
        request = ProcessingRequest(
            file_path=test_file,
            source_id="test_123",
            course_id="course_456",
            metadata={'test': True}
        )
        
        response = await manager.process_file(request)
        
        print(f"Success: {response.success}")
        print(f"Chunks: {len(response.chunks)}")
        print(f"Processing time: {response.processing_time_ms}ms")
        print(f"Was cached: {response.was_cached}")
        
        if response.chunks:
            print(f"First chunk: {response.chunks[0].content[:100]}...")
    else:
        print("No test file found")
        
        # Show statistics
        stats = await manager.get_processing_statistics()
        print(f"Statistics: {stats}")


if __name__ == "__main__":
    asyncio.run(main())