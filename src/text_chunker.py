#!/usr/bin/env python3
"""
Intelligent Text Chunker

Creates semantically aware text chunks with configurable overlap,
structure preservation, and metadata enrichment for optimal storage and retrieval.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import hashlib

# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


@dataclass
class TextChunk:
    """Container for a text chunk with metadata"""
    content: str
    chunk_id: str
    source_file_id: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    heading_level: Optional[int] = None
    metadata: Dict[str, Any] = None
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()


class TextChunker:
    """Intelligent text chunking with semantic awareness"""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 overlap: int = 200,
                 min_chunk_size: int = 100,
                 preserve_structure: bool = True):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        self.preserve_structure = preserve_structure
        self.logger = logging.getLogger(__name__)
        
        # Initialize tokenizer if available
        if TIKTOKEN_AVAILABLE:
            try:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
                self.logger.info("Using tiktoken for accurate token counting")
            except Exception as e:
                self.logger.warning(f"Failed to initialize tiktoken: {e}")
                self.tokenizer = None
        else:
            self.tokenizer = None
            self.logger.info("tiktoken not available, using word-based estimation")
    
    def chunk_text(self, 
                   text: str, 
                   source_file_id: str,
                   metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """
        Create semantically aware chunks from text
        
        Args:
            text: Text content to chunk
            source_file_id: Identifier for source file
            metadata: Additional metadata
            
        Returns:
            List of TextChunk objects
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []
        
        metadata = metadata or {}
        
        try:
            # Clean and normalize text
            cleaned_text = self._clean_text(text)
            
            # Detect document structure if preservation is enabled
            if self.preserve_structure:
                sections = self._detect_sections(cleaned_text)
                chunks = self._chunk_with_structure(sections, source_file_id, metadata)
            else:
                chunks = self._chunk_simple(cleaned_text, source_file_id, metadata)
            
            # Post-process chunks
            chunks = self._post_process_chunks(chunks)
            
            self.logger.info(f"Created {len(chunks)} chunks from text ({len(text)} chars)")
            return chunks
            
        except Exception as e:
            self.logger.error(f"Failed to chunk text: {e}")
            return []
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Normalize line breaks
        text = re.sub(r'\r\n|\r', '\n', text)
        
        return text.strip()
    
    def _detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """Detect document sections, headings, and structure"""
        sections = []
        lines = text.split('\n')
        current_section = {'title': None, 'content': [], 'start_line': 0, 'heading_level': 0}
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                if current_section['content']:
                    current_section['content'].append('')
                continue
            
            # Detect headings
            heading_level = self._detect_heading_level(line)
            
            if heading_level > 0:
                # Save previous section
                if current_section['content']:
                    current_section['content'] = [l for l in current_section['content'] if l.strip()]
                    if current_section['content']:
                        sections.append(current_section.copy())
                
                # Start new section
                current_section = {
                    'title': line,
                    'content': [],
                    'start_line': line_num,
                    'heading_level': heading_level
                }
            else:
                current_section['content'].append(line)
        
        # Add final section
        if current_section['content']:
            current_section['content'] = [l for l in current_section['content'] if l.strip()]
            if current_section['content']:
                sections.append(current_section)
        
        # If no sections detected, create a single section
        if not sections:
            sections = [{
                'title': None,
                'content': [line.strip() for line in lines if line.strip()],
                'start_line': 0,
                'heading_level': 0
            }]
        
        return sections
    
    def _detect_heading_level(self, line: str) -> int:
        """Detect if line is a heading and its level"""
        line = line.strip()
        
        # Empty lines are not headings
        if not line:
            return 0
        
        # Lines that are too long are probably not headings
        if len(line) > 200:
            return 0
        
        # Markdown-style headings
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            if level <= 6 and line[level:].strip():
                return level
        
        # All caps short lines (likely headings)
        if line.isupper() and len(line) < 100:
            return 2
        
        # Title case short lines
        if line.istitle() and len(line) < 80 and not line.endswith('.'):
            return 3
        
        # Lines ending with colon (section headers)
        if line.endswith(':') and len(line) < 100:
            return 4
        
        # Page markers
        if re.match(r'^\[?Page \d+\]?$', line, re.IGNORECASE):
            return 5
        
        return 0
    
    def _chunk_with_structure(self, 
                            sections: List[Dict[str, Any]], 
                            source_file_id: str,
                            metadata: Dict[str, Any]) -> List[TextChunk]:
        """Create chunks while preserving document structure"""
        chunks = []
        chunk_index = 0
        global_char_pos = 0
        
        for section in sections:
            section_title = section.get('title')
            section_content = '\n'.join(section['content'])
            heading_level = section.get('heading_level', 0)
            
            # Extract page/slide numbers from title or content
            page_number = self._extract_page_number(section_title or section_content)
            slide_number = self._extract_slide_number(section_title or section_content)
            
            if len(section_content) <= self.chunk_size:
                # Section fits in one chunk
                chunk = self._create_chunk(
                    content=section_content,
                    chunk_id=f"{source_file_id}_{chunk_index}",
                    source_file_id=source_file_id,
                    chunk_index=chunk_index,
                    char_start=global_char_pos,
                    char_end=global_char_pos + len(section_content),
                    section_title=section_title,
                    page_number=page_number,
                    slide_number=slide_number,
                    heading_level=heading_level,
                    metadata=metadata
                )
                chunks.append(chunk)
                chunk_index += 1
            else:
                # Split large section into multiple chunks
                section_chunks = self._split_section(
                    section_content,
                    source_file_id,
                    chunk_index,
                    global_char_pos,
                    section_title,
                    page_number,
                    slide_number,
                    heading_level,
                    metadata
                )
                chunks.extend(section_chunks)
                chunk_index += len(section_chunks)
            
            global_char_pos += len(section_content) + 2  # +2 for section separator
        
        return chunks
    
    def _chunk_simple(self, 
                     text: str, 
                     source_file_id: str,
                     metadata: Dict[str, Any]) -> List[TextChunk]:
        """Simple chunking without structure preservation"""
        chunks = []
        chunk_index = 0
        start_pos = 0
        
        while start_pos < len(text):
            end_pos = min(start_pos + self.chunk_size, len(text))
            
            # Try to break at sentence boundary
            if end_pos < len(text):
                # Look for sentence endings near the target position
                search_start = max(start_pos, end_pos - 200)
                search_text = text[search_start:end_pos + 200]
                
                sentence_endings = ['.', '!', '?', '\n\n']
                best_break = -1
                
                for ending in sentence_endings:
                    pos = search_text.rfind(ending)
                    if pos > len(search_text) // 2:  # Prefer breaks in latter half
                        best_break = search_start + pos + len(ending)
                        break
                
                if best_break > start_pos:
                    end_pos = best_break
            
            chunk_content = text[start_pos:end_pos].strip()
            
            if len(chunk_content) >= self.min_chunk_size:
                chunk = self._create_chunk(
                    content=chunk_content,
                    chunk_id=f"{source_file_id}_{chunk_index}",
                    source_file_id=source_file_id,
                    chunk_index=chunk_index,
                    char_start=start_pos,
                    char_end=end_pos,
                    metadata=metadata
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Calculate next start position with overlap
            start_pos = max(start_pos + 1, end_pos - self.overlap)
        
        return chunks
    
    def _split_section(self, 
                      content: str,
                      source_file_id: str,
                      start_chunk_index: int,
                      global_char_start: int,
                      section_title: Optional[str],
                      page_number: Optional[int],
                      slide_number: Optional[int],
                      heading_level: int,
                      metadata: Dict[str, Any]) -> List[TextChunk]:
        """Split a large section into multiple chunks"""
        chunks = []
        chunk_index = start_chunk_index
        start_pos = 0
        
        while start_pos < len(content):
            end_pos = min(start_pos + self.chunk_size, len(content))
            
            # Try to break at paragraph boundary
            if end_pos < len(content):
                para_break = content.rfind('\n\n', start_pos, end_pos + 100)
                if para_break > start_pos:
                    end_pos = para_break
            
            chunk_content = content[start_pos:end_pos].strip()
            
            if len(chunk_content) >= self.min_chunk_size:
                chunk = self._create_chunk(
                    content=chunk_content,
                    chunk_id=f"{source_file_id}_{chunk_index}",
                    source_file_id=source_file_id,
                    chunk_index=chunk_index,
                    char_start=global_char_start + start_pos,
                    char_end=global_char_start + end_pos,
                    section_title=section_title,
                    page_number=page_number,
                    slide_number=slide_number,
                    heading_level=heading_level,
                    metadata=metadata
                )
                chunks.append(chunk)
                chunk_index += 1
            
            start_pos = max(start_pos + 1, end_pos - self.overlap)
        
        return chunks
    
    def _create_chunk(self, **kwargs) -> TextChunk:
        """Create a TextChunk with token counting"""
        content = kwargs.get('content', '')
        token_count = self._count_tokens(content)
        
        return TextChunk(
            token_count=token_count,
            **kwargs
        )
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if not text:
            return 0
        
        if self.tokenizer:
            try:
                return len(self.tokenizer.encode(text))
            except Exception as e:
                self.logger.warning(f"Token counting failed: {e}")
        
        # Fallback: estimate based on words (rough approximation)
        words = len(text.split())
        return int(words * 1.3)  # Average 1.3 tokens per word
    
    def _extract_page_number(self, text: str) -> Optional[int]:
        """Extract page number from text"""
        if not text:
            return None
        
        # Look for patterns like "Page 5", "[Page 5]", etc.
        match = re.search(r'\[?Page\s+(\d+)\]?', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None
    
    def _extract_slide_number(self, text: str) -> Optional[int]:
        """Extract slide number from text"""
        if not text:
            return None
        
        # Look for patterns like "Slide 3", "[Slide 3]", etc.
        match = re.search(r'\[?Slide\s+(\d+)\]?', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None
    
    def _post_process_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Post-process chunks for quality and consistency"""
        if not chunks:
            return chunks
        
        # Remove very small chunks (merge with next if possible)
        filtered_chunks = []
        i = 0
        
        while i < len(chunks):
            chunk = chunks[i]
            
            if len(chunk.content) < self.min_chunk_size and i < len(chunks) - 1:
                # Try to merge with next chunk
                next_chunk = chunks[i + 1]
                merged_content = chunk.content + "\n\n" + next_chunk.content
                
                if len(merged_content) <= self.chunk_size * 1.2:  # Allow 20% overage
                    # Merge chunks
                    merged_chunk = TextChunk(
                        content=merged_content,
                        chunk_id=chunk.chunk_id,
                        source_file_id=chunk.source_file_id,
                        chunk_index=chunk.chunk_index,
                        char_start=chunk.char_start,
                        char_end=next_chunk.char_end,
                        token_count=self._count_tokens(merged_content),
                        section_title=chunk.section_title or next_chunk.section_title,
                        page_number=chunk.page_number or next_chunk.page_number,
                        slide_number=chunk.slide_number or next_chunk.slide_number,
                        heading_level=chunk.heading_level or next_chunk.heading_level,
                        metadata=chunk.metadata
                    )
                    filtered_chunks.append(merged_chunk)
                    i += 2  # Skip next chunk as it's been merged
                    continue
            
            filtered_chunks.append(chunk)
            i += 1
        
        # Update chunk indices
        for idx, chunk in enumerate(filtered_chunks):
            chunk.chunk_index = idx
            chunk.chunk_id = f"{chunk.source_file_id}_{idx}"
        
        return filtered_chunks


async def main():
    """Test the text chunker"""
    logging.basicConfig(level=logging.INFO)
    
    chunker = TextChunker(chunk_size=500, overlap=100)
    
    # Test text with structure
    test_text = """
    # Introduction to Machine Learning
    
    Machine learning is a subset of artificial intelligence that focuses on algorithms.
    
    ## What is Machine Learning?
    
    Machine learning algorithms build mathematical models based on training data.
    These models can make predictions or decisions without being explicitly programmed.
    
    ### Types of Machine Learning
    
    There are three main types:
    1. Supervised learning
    2. Unsupervised learning  
    3. Reinforcement learning
    
    ## Applications
    
    Machine learning is used in various domains including:
    - Healthcare
    - Finance
    - Transportation
    - Entertainment
    """
    
    chunks = chunker.chunk_text(test_text, "test_file_123")
    
    print(f"Created {len(chunks)} chunks:")
    for chunk in chunks:
        print(f"\nChunk {chunk.chunk_index}:")
        print(f"  Title: {chunk.section_title}")
        print(f"  Length: {len(chunk.content)} chars, {chunk.token_count} tokens")
        print(f"  Content preview: {chunk.content[:100]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())