#!/usr/bin/env python3
"""
Simple script to get active courses from Canvas API
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from canvas_client import CanvasClient

async def get_active_courses():
    """Get and display active courses"""
    client = CanvasClient()
    
    try:
        courses = await client.get_active_courses()
        
        print("Active Courses Found:")
        print("=" * 50)
        
        for course in courses:
            print(f"ID: {course['id']}")
            print(f"Name: {course['name']}")
            print("-" * 30)
        
        print(f"\nTotal: {len(courses)} active courses")
        
        # Also save to JSON for easy reference
        with open('active_courses.json', 'w') as f:
            json.dump(courses, f, indent=2)
        print("\nCourses saved to active_courses.json")
        
    except Exception as e:
        print(f"Error retrieving courses: {e}")

if __name__ == "__main__":
    asyncio.run(get_active_courses())