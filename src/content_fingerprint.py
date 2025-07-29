#!/usr/bin/env python3
"""
Content Fingerprinting System

Generates unique fingerprints for Canvas content to enable deduplication
and change detection. Uses SHA-256 hashing for reliable content identification.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class ContentFingerprint:
    """Container for content fingerprint information"""
    fingerprint: str
    content_type: str  # 'file', 'page', 'module', 'course'
    entity_id: str     # Canvas ID
    created_at: datetime
    metadata: Dict[str, Any]


class FingerprintGenerator:
    """Generates content fingerprints for deduplication"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_file_fingerprint(self, file_info: Dict[str, Any]) -> str:
        """
        Generate fingerprint for a Canvas file
        
        Args:
            file_info: Canvas file information dictionary
            
        Returns:
            SHA-256 hash string
        """
        try:
            # Key components for file fingerprinting
            components = {
                'id': file_info.get('id'),
                'size': file_info.get('size'),
                'updated_at': file_info.get('updated_at'),
                'content_type': file_info.get('content-type'),
                'display_name': file_info.get('display_name')
            }
            
            # Create stable string representation
            content_string = json.dumps(components, sort_keys=True, separators=(',', ':'))
            
            # Generate SHA-256 hash
            fingerprint = hashlib.sha256(content_string.encode('utf-8')).hexdigest()
            
            self.logger.debug(f"Generated file fingerprint: {fingerprint[:12]}... for file {components['id']}")
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Failed to generate file fingerprint: {e}")
            # Fallback to basic ID-based fingerprint
            return hashlib.sha256(str(file_info.get('id', 'unknown')).encode()).hexdigest()
    
    def generate_module_fingerprint(self, module_info: Dict[str, Any], items: Optional[list] = None) -> str:
        """
        Generate fingerprint for a Canvas module
        
        Args:
            module_info: Canvas module information
            items: List of module items (optional)
            
        Returns:
            SHA-256 hash string
        """
        try:
            # Key components for module fingerprinting
            components = {
                'id': module_info.get('id'),
                'updated_at': module_info.get('updated_at'),
                'items_count': module_info.get('items_count'),
                'name': module_info.get('name')
            }
            
            # Include item fingerprints if provided
            if items:
                item_fingerprints = []
                for item in items:
                    item_fp = self.generate_item_fingerprint(item)
                    item_fingerprints.append(item_fp)
                components['items_hash'] = hashlib.sha256(
                    ':'.join(sorted(item_fingerprints)).encode()
                ).hexdigest()
            
            content_string = json.dumps(components, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(content_string.encode('utf-8')).hexdigest()
            
            self.logger.debug(f"Generated module fingerprint: {fingerprint[:12]}... for module {components['id']}")
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Failed to generate module fingerprint: {e}")
            return hashlib.sha256(str(module_info.get('id', 'unknown')).encode()).hexdigest()
    
    def generate_item_fingerprint(self, item_info: Dict[str, Any]) -> str:
        """
        Generate fingerprint for a Canvas module item
        
        Args:
            item_info: Canvas module item information
            
        Returns:
            SHA-256 hash string
        """
        try:
            components = {
                'id': item_info.get('id'),
                'type': item_info.get('type'),
                'content_id': item_info.get('content_id'),
                'updated_at': item_info.get('updated_at'),
                'title': item_info.get('title')
            }
            
            content_string = json.dumps(components, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(content_string.encode('utf-8')).hexdigest()
            
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Failed to generate item fingerprint: {e}")
            return hashlib.sha256(str(item_info.get('id', 'unknown')).encode()).hexdigest()
    
    def generate_page_fingerprint(self, page_info: Dict[str, Any], content: Optional[str] = None) -> str:
        """
        Generate fingerprint for a Canvas page
        
        Args:
            page_info: Canvas page information
            content: Page content (optional)
            
        Returns:
            SHA-256 hash string
        """
        try:
            components = {
                'url': page_info.get('url'),
                'updated_at': page_info.get('updated_at'),
                'title': page_info.get('title')
            }
            
            # Include content hash if provided
            if content:
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                components['content_hash'] = content_hash
            
            content_string = json.dumps(components, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(content_string.encode('utf-8')).hexdigest()
            
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Failed to generate page fingerprint: {e}")
            return hashlib.sha256(str(page_info.get('url', 'unknown')).encode()).hexdigest()
    
    def generate_course_fingerprint(self, course_info: Dict[str, Any]) -> str:
        """
        Generate fingerprint for a Canvas course
        
        Args:
            course_info: Canvas course information
            
        Returns:
            SHA-256 hash string
        """
        try:
            components = {
                'id': course_info.get('id'),
                'updated_at': course_info.get('updated_at'),
                'name': course_info.get('name'),
                'course_code': course_info.get('course_code')
            }
            
            content_string = json.dumps(components, sort_keys=True, separators=(',', ':'))
            fingerprint = hashlib.sha256(content_string.encode('utf-8')).hexdigest()
            
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Failed to generate course fingerprint: {e}")
            return hashlib.sha256(str(course_info.get('id', 'unknown')).encode()).hexdigest()
    
    def generate_text_content_fingerprint(self, text: str) -> str:
        """
        Generate fingerprint for extracted text content
        
        Args:
            text: Text content
            
        Returns:
            SHA-256 hash string
        """
        try:
            # Normalize text (remove extra whitespace, standardize line endings)
            normalized_text = ' '.join(text.split())
            fingerprint = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
            
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Failed to generate text fingerprint: {e}")
            return hashlib.sha256(b'empty').hexdigest()
    
    def create_fingerprint_record(self, 
                                fingerprint: str, 
                                content_type: str, 
                                entity_id: str, 
                                metadata: Dict[str, Any] = None) -> ContentFingerprint:
        """
        Create a ContentFingerprint record
        
        Args:
            fingerprint: The generated fingerprint
            content_type: Type of content ('file', 'page', 'module', 'course')
            entity_id: Canvas entity ID
            metadata: Additional metadata
            
        Returns:
            ContentFingerprint object
        """
        return ContentFingerprint(
            fingerprint=fingerprint,
            content_type=content_type,
            entity_id=entity_id,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
    
    def verify_fingerprint(self, content: Any, expected_fingerprint: str, content_type: str) -> bool:
        """
        Verify that content matches expected fingerprint
        
        Args:
            content: Content to verify
            expected_fingerprint: Expected fingerprint value
            content_type: Type of content for appropriate fingerprint generation
            
        Returns:
            True if fingerprints match, False otherwise
        """
        try:
            if content_type == 'file':
                actual_fingerprint = self.generate_file_fingerprint(content)
            elif content_type == 'module':
                actual_fingerprint = self.generate_module_fingerprint(content)
            elif content_type == 'page':
                actual_fingerprint = self.generate_page_fingerprint(content)
            elif content_type == 'course':
                actual_fingerprint = self.generate_course_fingerprint(content)
            elif content_type == 'text':
                actual_fingerprint = self.generate_text_content_fingerprint(content)
            else:
                self.logger.error(f"Unknown content type for verification: {content_type}")
                return False
            
            matches = actual_fingerprint == expected_fingerprint
            if not matches:
                self.logger.warning(f"Fingerprint mismatch for {content_type}: "
                                  f"expected {expected_fingerprint[:12]}..., "
                                  f"got {actual_fingerprint[:12]}...")
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Failed to verify fingerprint: {e}")
            return False


def main():
    """Test fingerprint generation"""
    logging.basicConfig(level=logging.INFO)
    
    generator = FingerprintGenerator()
    
    # Test file fingerprint
    file_info = {
        'id': 12345,
        'size': 1024768,
        'updated_at': '2024-01-15T10:30:00Z',
        'content-type': 'application/pdf',
        'display_name': 'lecture_notes.pdf'
    }
    
    file_fp = generator.generate_file_fingerprint(file_info)
    print(f"File fingerprint: {file_fp}")
    
    # Test module fingerprint
    module_info = {
        'id': 67890,
        'updated_at': '2024-01-15T10:30:00Z',
        'items_count': 5,
        'name': 'Week 1: Introduction'
    }
    
    module_fp = generator.generate_module_fingerprint(module_info)
    print(f"Module fingerprint: {module_fp}")
    
    # Test text fingerprint
    text_content = "This is sample text content for fingerprinting."
    text_fp = generator.generate_text_content_fingerprint(text_content)
    print(f"Text fingerprint: {text_fp}")
    
    # Test verification
    is_valid = generator.verify_fingerprint(file_info, file_fp, 'file')
    print(f"File fingerprint verification: {is_valid}")


if __name__ == "__main__":
    main()