"""
File Processors Package

Multi-format file processing for Canvas content including PDF, PPTX, DOCX,
and other document formats with intelligent text extraction.
"""

from .base_processor import BaseFileProcessor, ProcessingResult, ExtractionMetadata
from .pdf_processor import PDFProcessor
from .pptx_processor import PPTXProcessor
from .docx_processor import WordProcessor

__all__ = [
    'BaseFileProcessor',
    'ProcessingResult', 
    'ExtractionMetadata',
    'PDFProcessor',
    'PPTXProcessor',
    'WordProcessor'
]