#!/usr/bin/env python3
"""
PDF Processor

Advanced PDF text extraction with layout preservation, table detection,
and fallback mechanisms for various PDF types including scanned documents.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from .base_processor import BaseFileProcessor, ProcessingResult, ExtractionMetadata

# PDF processing libraries
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF for image extraction
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class PDFProcessor(BaseFileProcessor):
    """Advanced PDF text extraction processor"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pdf']
        self.supported_mime_types = ['application/pdf']
        
        # Check available libraries
        self.pdfplumber_available = PDFPLUMBER_AVAILABLE
        self.pypdf2_available = PYPDF2_AVAILABLE
        self.ocr_available = OCR_AVAILABLE
        
        if not (self.pdfplumber_available or self.pypdf2_available):
            self.logger.error("No PDF processing libraries available")
    
    async def extract_text(self, file_path: Path) -> ProcessingResult:
        """Extract text from PDF using multiple methods"""
        start_time = time.time()
        
        try:
            # Try pdfplumber first (best for layout-aware extraction)
            if self.pdfplumber_available:
                result = await self._extract_with_pdfplumber(file_path)
                if result.success and len(result.text_content.strip()) > 50:
                    result.metadata.processing_time_ms = int((time.time() - start_time) * 1000)
                    return result
                else:
                    self.logger.info(f"pdfplumber extraction insufficient for {file_path}, trying fallback")
            
            # Fallback to PyPDF2
            if self.pypdf2_available:
                result = await self._extract_with_pypdf2(file_path)
                if result.success and len(result.text_content.strip()) > 50:
                    result.metadata.processing_time_ms = int((time.time() - start_time) * 1000)
                    return result
                else:
                    self.logger.info(f"PyPDF2 extraction insufficient for {file_path}, trying OCR")
            
            # Last resort: OCR for scanned PDFs
            if self.ocr_available:
                result = await self._extract_with_ocr(file_path)
                result.metadata.processing_time_ms = int((time.time() - start_time) * 1000)
                return result
            
            # No extraction methods available or all failed
            processing_time_ms = int((time.time() - start_time) * 1000)
            metadata = self._create_base_metadata(file_path, processing_time_ms)
            metadata.errors.append("No suitable PDF extraction method available or all methods failed")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            metadata = self._create_base_metadata(file_path, processing_time_ms)
            metadata.errors.append(f"PDF processing error: {str(e)}")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
    
    async def _extract_with_pdfplumber(self, file_path: Path) -> ProcessingResult:
        """Extract text using pdfplumber (layout-aware)"""
        try:
            text_content = []
            structured_content = {'pages': [], 'tables': [], 'images': []}
            has_tables = False
            has_images = False
            total_chars = 0
            
            with pdfplumber.open(file_path) as pdf:
                # Extract metadata
                metadata = self._create_base_metadata(file_path, 0)
                metadata.page_count = len(pdf.pages)
                
                # Extract document metadata
                if pdf.metadata:
                    metadata.title = pdf.metadata.get('Title')
                    metadata.author = pdf.metadata.get('Author')
                    metadata.subject = pdf.metadata.get('Subject')
                    metadata.creation_date = pdf.metadata.get('CreationDate')
                    
                    keywords = pdf.metadata.get('Keywords')
                    if keywords:
                        metadata.keywords = [k.strip() for k in keywords.split(',')]
                
                # Process each page
                for page_num, page in enumerate(pdf.pages, 1):
                    page_data = {'page': page_num, 'text': '', 'tables': [], 'images': []}
                    
                    # Extract text
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        page_data['text'] = page_text
                        text_content.append(f"[Page {page_num}]\n{page_text}")
                        total_chars += len(page_text)
                    
                    # Extract tables
                    tables = page.find_tables()
                    if tables:
                        has_tables = True
                        for table_idx, table in enumerate(tables):
                            try:
                                table_data = table.extract()
                                if table_data:
                                    table_info = {
                                        'page': page_num,
                                        'table_index': table_idx,
                                        'rows': len(table_data),
                                        'columns': len(table_data[0]) if table_data else 0,
                                        'data': table_data[:5]  # First 5 rows only
                                    }
                                    page_data['tables'].append(table_info)
                                    structured_content['tables'].append(table_info)
                                    
                                    # Add table content to text
                                    table_text = self._table_to_text(table_data)
                                    text_content.append(f"[Page {page_num} Table {table_idx + 1}]\n{table_text}")
                            except Exception as e:
                                self.logger.warning(f"Failed to extract table {table_idx} on page {page_num}: {e}")
                    
                    # Check for images
                    if hasattr(page, 'images') and page.images:
                        has_images = True
                        page_data['images'] = [{'count': len(page.images)}]
                    
                    structured_content['pages'].append(page_data)
                
                # Combine all text
                full_text = "\n\n".join(text_content)
                normalized_text = self._normalize_text(full_text)
                
                # Update metadata
                metadata.character_count = len(normalized_text)
                metadata.word_count = self._count_words(normalized_text)
                metadata.language = self._detect_language(normalized_text)
                metadata.has_tables = has_tables
                metadata.has_images = has_images
                metadata.extraction_method = "pdfplumber"
                
                return ProcessingResult(
                    success=True,
                    text_content=normalized_text,
                    metadata=metadata,
                    structured_content=structured_content
                )
                
        except Exception as e:
            self.logger.error(f"pdfplumber extraction failed for {file_path}: {e}")
            metadata = self._create_base_metadata(file_path, 0)
            metadata.errors.append(f"pdfplumber error: {str(e)}")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
    
    async def _extract_with_pypdf2(self, file_path: Path) -> ProcessingResult:
        """Extract text using PyPDF2 (fallback method)"""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Create metadata
                metadata = self._create_base_metadata(file_path, 0)
                metadata.page_count = len(pdf_reader.pages)
                metadata.extraction_method = "PyPDF2"
                
                # Extract document metadata
                if pdf_reader.metadata:
                    metadata.title = pdf_reader.metadata.get('/Title')
                    metadata.author = pdf_reader.metadata.get('/Author')
                    metadata.subject = pdf_reader.metadata.get('/Subject')
                    
                    # Handle creation date
                    creation_date = pdf_reader.metadata.get('/CreationDate')
                    if creation_date:
                        try:
                            # PyPDF2 dates are in format D:YYYYMMDDHHmmSSOHH'mm'
                            if creation_date.startswith('D:'):
                                date_str = creation_date[2:16]  # Extract YYYYMMDDHHMMSS
                                metadata.creation_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
                        except Exception:
                            pass
                
                # Extract text from all pages
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(f"[Page {page_num}]\n{page_text}")
                    except Exception as e:
                        self.logger.warning(f"Failed to extract text from page {page_num}: {e}")
                        metadata.warnings.append(f"Page {page_num} extraction failed")
                
                # Combine and normalize text
                full_text = "\n\n".join(text_content)
                normalized_text = self._normalize_text(full_text)
                
                # Update metadata
                metadata.character_count = len(normalized_text)
                metadata.word_count = self._count_words(normalized_text)
                metadata.language = self._detect_language(normalized_text)
                
                return ProcessingResult(
                    success=len(normalized_text.strip()) > 0,
                    text_content=normalized_text,
                    metadata=metadata
                )
                
        except Exception as e:
            self.logger.error(f"PyPDF2 extraction failed for {file_path}: {e}")
            metadata = self._create_base_metadata(file_path, 0)
            metadata.errors.append(f"PyPDF2 error: {str(e)}")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
    
    async def _extract_with_ocr(self, file_path: Path) -> ProcessingResult:
        """Extract text using OCR (for scanned PDFs)"""
        try:
            text_content = []
            
            # Open PDF with PyMuPDF for image extraction
            pdf_document = fitz.open(file_path)
            
            metadata = self._create_base_metadata(file_path, 0)
            metadata.page_count = len(pdf_document)
            metadata.extraction_method = "OCR (Tesseract)"
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Convert page to image
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image
                image = Image.open(io.BytesIO(img_data))
                
                # Perform OCR
                try:
                    page_text = pytesseract.image_to_string(image, lang='eng')
                    if page_text.strip():
                        text_content.append(f"[Page {page_num + 1} OCR]\n{page_text}")
                except Exception as e:
                    self.logger.warning(f"OCR failed for page {page_num + 1}: {e}")
                    metadata.warnings.append(f"OCR failed for page {page_num + 1}")
            
            pdf_document.close()
            
            # Combine and normalize text
            full_text = "\n\n".join(text_content)
            normalized_text = self._normalize_text(full_text)
            
            # Update metadata
            metadata.character_count = len(normalized_text)
            metadata.word_count = self._count_words(normalized_text)
            metadata.language = self._detect_language(normalized_text)
            
            if len(normalized_text.strip()) > 0:
                metadata.warnings.append("Text extracted using OCR - accuracy may vary")
            
            return ProcessingResult(
                success=len(normalized_text.strip()) > 0,
                text_content=normalized_text,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"OCR extraction failed for {file_path}: {e}")
            metadata = self._create_base_metadata(file_path, 0)
            metadata.errors.append(f"OCR error: {str(e)}")
            
            return ProcessingResult(
                success=False,
                text_content="",
                metadata=metadata
            )
    
    def _table_to_text(self, table_data: List[List[str]]) -> str:
        """Convert table data to readable text format"""
        if not table_data:
            return ""
        
        lines = []
        for row in table_data:
            if row:  # Skip empty rows
                # Join cells with tab separator and clean up
                cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                lines.append("\t".join(cleaned_row))
        
        return "\n".join(lines)


# Test function
async def main():
    """Test PDF processor"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    logging.basicConfig(level=logging.INFO)
    
    processor = PDFProcessor()
    
    # Test with a sample PDF file (you would need to provide a real file)
    test_file = Path("sample.pdf")
    if test_file.exists():
        result = await processor.extract_text(test_file)
        
        print(f"Success: {result.success}")
        print(f"Text length: {len(result.text_content)}")
        print(f"Pages: {result.metadata.page_count}")
        print(f"Method: {result.metadata.extraction_method}")
        print(f"Processing time: {result.metadata.processing_time_ms}ms")
        
        if result.metadata.errors:
            print(f"Errors: {result.metadata.errors}")
        
        if result.text_content:
            print(f"Text preview: {result.text_content[:200]}...")
    else:
        print("No test PDF file found")


if __name__ == "__main__":
    asyncio.run(main())