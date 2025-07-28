#!/usr/bin/env python3
"""
Word Document Processor

Extract text content from DOCX files with structure preservation.
"""

import asyncio
import time
from pathlib import Path
from .base_processor import BaseFileProcessor, ProcessingResult

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class WordProcessor(BaseFileProcessor):
    """Word DOCX file processor"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.docx']
        self.supported_mime_types = ['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        self.docx_available = DOCX_AVAILABLE
    
    async def extract_text(self, file_path: Path) -> ProcessingResult:
        """Extract text from Word document"""
        start_time = time.time()
        
        if not self.docx_available:
            metadata = self._create_base_metadata(file_path, 0)
            metadata.errors.append("python-docx library not available")
            return ProcessingResult(success=False, text_content="", metadata=metadata)
        
        try:
            doc = Document(file_path)
            paragraphs = []
            
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    paragraphs.append(text)
            
            full_text = "\n".join(paragraphs)
            normalized_text = self._normalize_text(full_text)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            metadata = self._create_base_metadata(file_path, processing_time_ms)
            metadata.character_count = len(normalized_text)
            metadata.word_count = self._count_words(normalized_text)
            metadata.extraction_method = "python-docx"
            
            return ProcessingResult(
                success=True,
                text_content=normalized_text,
                metadata=metadata
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            metadata = self._create_base_metadata(file_path, processing_time_ms)
            metadata.errors.append(f"DOCX processing error: {str(e)}")
            return ProcessingResult(success=False, text_content="", metadata=metadata)