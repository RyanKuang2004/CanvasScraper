#!/usr/bin/env python3
"""
Demo script showing how to use the new get_assignments and get_quizzes functions
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.canvas_client import CanvasClient
import aiohttp

async def demo_assignments_and_quizzes():
    """Demonstrate the new assignment and quiz functions"""
    
    client = CanvasClient()
    
    # Test with Machine Learning course (might have quizzes)
    course_id = 213800  # Machine Learning Applications for Health
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"Fetching assignments and quizzes for course {course_id}...")
            print("=" * 60)
            
            # Get assignments
            assignments = await client.get_assignments(session, course_id)
            print(f"\n📝 ASSIGNMENTS ({len(assignments)} found):")
            print("-" * 40)
            
            for i, assignment in enumerate(assignments, 1):
                print(f"{i}. {assignment['name']}")
                print(f"   Due: {assignment['due_at'] or 'No due date'}")
                print(f"   Type: {assignment['type']}")
                if assignment['description']:
                    desc = assignment['description'][:150] + "..." if len(assignment['description']) > 150 else assignment['description']
                    print(f"   Description: {desc}")
                print()
            
            # Get quizzes  
            quizzes = await client.get_quizzes(session, course_id)
            print(f"\n🧠 QUIZZES ({len(quizzes)} found):")
            print("-" * 40)
            
            for i, quiz in enumerate(quizzes, 1):
                print(f"{i}. {quiz['name']}")
                print(f"   Due: {quiz['due_at'] or 'No due date'}")
                print(f"   Type: {quiz['type']}")
                if quiz['description']:
                    desc = quiz['description'][:150] + "..." if len(quiz['description']) > 150 else quiz['description']
                    print(f"   Description: {desc}")
                print()
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(demo_assignments_and_quizzes())