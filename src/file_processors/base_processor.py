#!/usr/bin/env python3
"""
Base File Processor

Abstract base class for file processing with common functionality
for text extraction, metadata handling, and error management.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import mimetypes


@dataclass
class ExtractionMetadata:
    """Metadata from file extraction process"""
    file_path: Path
    file_size: int
    content_type: str
    extraction_method: str
    processing_time_ms: int
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    language: Optional[str] = None
    creation_date: Optional[datetime] = None
    author: Optional[str] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    has_images: bool = False
    has_tables: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ProcessingResult:
    """Result of file processing operation"""
    success: bool
    text_content: str
    metadata: ExtractionMetadata
    structured_content: Optional[Dict[str, Any]] = None
    extracted_images: List[Dict[str, Any]] = field(default_factory=list)
    extracted_tables: List[Dict[str, Any]] = field(default_factory=list)
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.content_hash is None and self.text_content:
            self.content_hash = hashlib.sha256(self.text_content.encode('utf-8')).hexdigest()


class BaseFileProcessor(ABC):
    """Abstract base class for file processors"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.supported_extensions: List[str] = []
        self.supported_mime_types: List[str] = []
    
    @abstractmethod
    async def extract_text(self, file_path: Path) -> ProcessingResult:
        """
        Extract text content from file
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            ProcessingResult with extracted content and metadata
        """
        pass
    
    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if processor can handle this file type
        """
        # Check by extension
        extension = file_path.suffix.lower()
        if extension in self.supported_extensions:
            return True
        
        # Check by MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type in self.supported_mime_types:
            return True
        
        return False
    
    def _create_base_metadata(self, file_path: Path, processing_time_ms: int) -> ExtractionMetadata:
        """Create base metadata for a file"""
        try:
            file_stats = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            return ExtractionMetadata(
                file_path=file_path,
                file_size=file_stats.st_size,
                content_type=mime_type or 'application/octet-stream',
                extraction_method=self.__class__.__name__,
                processing_time_ms=processing_time_ms,
                creation_date=datetime.fromtimestamp(file_stats.st_ctime)
            )
        except Exception as e:
            self.logger.error(f"Failed to create base metadata: {e}")
            return ExtractionMetadata(
                file_path=file_path,
                file_size=0,
                content_type='unknown',
                extraction_method=self.__class__.__name__,
                processing_time_ms=processing_time_ms,
                errors=[f"Metadata error: {str(e)}"]
            )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text"""
        if not text:
            return ""
        
        # Replace multiple whitespace with single space
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _count_words(self, text: str) -> int:
        """Count words in text"""
        if not text:
            return 0
        return len(text.split())
    
    def _detect_language(self, text: str) -> Optional[str]:
        """Detect language of text (basic implementation)"""
        # This is a placeholder - in production you might use langdetect or similar
        if not text or len(text) < 50:
            return None
        
        # Simple heuristic - if mostly English characters, assume English
        english_chars = sum(1 for c in text.lower() if c in 'abcdefghijklmnopqrstuvwxyz ')
        total_chars = len(text)
        
        if total_chars > 0 and (english_chars / total_chars) > 0.7:
            return 'en'
        
        return 'unknown'
    
    async def process_with_timeout(self, file_path: Path, timeout_seconds: int = 300) -> ProcessingResult:
        """
        Process file with timeout
        
        Args:
            file_path: Path to file
            timeout_seconds: Processing timeout in seconds
            
        Returns:
            ProcessingResult
        """
        try:
            result = await asyncio.wait_for(
                self.extract_text(file_path),
                timeout=timeout_seconds
            )
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(f"Processing timeout for {file_path} after {timeout_seconds}s")
            metadata = self._create_base_metadata(file_path, timeout_seconds * 1000)
            metadata.errors.append(f"Processing timeout after {timeout_seconds}s")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
        except Exception as e:
            self.logger.error(f"Processing failed for {file_path}: {e}")
            metadata = self._create_base_metadata(file_path, 0)
            metadata.errors.append(f"Processing error: {str(e)}")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
    
    def _extract_basic_structure(self, text: str) -> Dict[str, Any]:
        """Extract basic structure from text (headings, paragraphs)"""
        if not text:
            return {}
        
        lines = text.split('\n')
        structure = {
            'total_lines': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'paragraphs': [],
            'headings': []
        }
        
        current_paragraph = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_paragraph:
                    structure['paragraphs'].append(' '.join(current_paragraph))
                    current_paragraph = []
                continue
            
            # Simple heading detection (lines that are short and might be headings)
            if len(line) < 100 and (line.isupper() or line.istitle()):
                structure['headings'].append(line)
            
            current_paragraph.append(line)
        
        # Add final paragraph
        if current_paragraph:
            structure['paragraphs'].append(' '.join(current_paragraph))
        
        return structure
    
    def validate_result(self, result: ProcessingResult) -> bool:
        """Validate processing result"""
        if not result:
            return False
        
        # Check for minimum content
        if result.success and len(result.text_content.strip()) < 10:
            result.metadata.warnings.append("Very little text content extracted")
        
        # Check for suspicious patterns
        if result.text_content and len(set(result.text_content)) < 10:
            result.metadata.warnings.append("Text content appears to have low diversity")
        
        return True


class FileProcessorFactory:
    """Factory for creating appropriate file processors"""
    
    def __init__(self):
        self.processors = {}
        self.logger = logging.getLogger(__name__)
    
    def register_processor(self, processor_class, extensions: List[str], mime_types: List[str] = None):
        """Register a file processor"""
        for ext in extensions:
            self.processors[ext.lower()] = processor_class
        
        if mime_types:
            for mime_type in mime_types:
                self.processors[mime_type] = processor_class
    
    def get_processor(self, file_path: Path) -> Optional[BaseFileProcessor]:
        """Get appropriate processor for file"""
        # Try by extension first
        extension = file_path.suffix.lower()
        if extension in self.processors:
            return self.processors[extension]()
        
        # Try by MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type in self.processors:
            return self.processors[mime_type]()
        
        self.logger.warning(f"No processor found for {file_path}")
        return None
    
    async def process_file(self, file_path: Path, timeout_seconds: int = 300) -> Optional[ProcessingResult]:
        """Process a file using appropriate processor"""
        processor = self.get_processor(file_path)
        if not processor:
            return None
        
        return await processor.process_with_timeout(file_path, timeout_seconds)