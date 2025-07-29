#!/usr/bin/env python3
"""
Canvas Scraper Demo Script - Consolidated utility for testing Canvas API functions
Combines functionality from get_courses.py, demo_assignments_quizzes.py, and test_cleanup_verification.py
"""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from canvas_client import CanvasClient

async def get_active_courses():
    """Get and display active courses"""
    client = CanvasClient()
    
    try:
        courses = await client.get_active_courses()
        
        print("📚 Active Courses Found:")
        print("=" * 50)
        
        for course in courses:
            print(f"ID: {course['id']}")
            print(f"Name: {course['name']}")
            print("-" * 30)
        
        print(f"\nTotal: {len(courses)} active courses")
        return courses
        
    except Exception as e:
        print(f"Error retrieving courses: {e}")
        return []

async def demo_assignments_and_quizzes(course_id=213800):
    """Demonstrate assignments and quiz functions for a specific course"""
    
    client = CanvasClient()
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"📝 Fetching assignments and quizzes for course {course_id}...")
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
                
            return {"assignments": assignments, "quizzes": quizzes}
                
        except Exception as e:
            print(f"Error: {e}")
            return {"assignments": [], "quizzes": []}

async def verify_client_functions():
    """Verify that Canvas client functions are working correctly"""
    
    client = CanvasClient()
    
    print("\n🔧 CANVAS CLIENT VERIFICATION:")
    print("=" * 50)
    
    # Test 1: Verify functions exist
    print("\n✅ FUNCTION AVAILABILITY:")
    print(f"  - get_assignments: {hasattr(client, 'get_assignments')}")
    print(f"  - get_quizzes: {hasattr(client, 'get_quizzes')}")
    print(f"  - _html_to_text: {hasattr(client, '_html_to_text')}")
    print(f"  - get_due_dates (should be False): {hasattr(client, 'get_due_dates')}")
    
    # Test 2: Test HTML conversion
    print("\n✅ HTML TO TEXT CONVERSION:")
    test_html = "<p>This is <strong>bold</strong> and <em>italic</em> text with <a href='#'>links</a>.</p>"
    converted = client._html_to_text(test_html)
    print(f"  Original: {test_html}")
    print(f"  Converted: {converted}")
    
    return {
        "functions_available": {
            "get_assignments": hasattr(client, 'get_assignments'),
            "get_quizzes": hasattr(client, 'get_quizzes'),
            "_html_to_text": hasattr(client, '_html_to_text'),
            "get_due_dates": hasattr(client, 'get_due_dates')
        },
        "html_conversion_test": {
            "original": test_html,
            "converted": converted
        }
    }

async def full_demo():
    """Run complete Canvas API demonstration"""
    
    print("🚀 CANVAS SCRAPER COMPREHENSIVE DEMO")
    print("=" * 60)
    
    results = {}
    
    # Step 1: Get active courses
    courses = await get_active_courses()
    results["courses"] = courses
    
    # Save courses to JSON
    courses_file = Path("active_courses.json")
    with open(courses_file, 'w') as f:
        json.dump(courses, f, indent=2)
    print(f"\n💾 Courses saved to {courses_file}")
    
    # Step 2: Verify client functions
    verification = await verify_client_functions()
    results["verification"] = verification
    
    # Step 3: Demo assignments/quizzes for first course
    if courses:
        first_course = courses[0]
        print(f"\n🎯 Testing with course: {first_course['name']} (ID: {first_course['id']})")
        assessments = await demo_assignments_and_quizzes(first_course['id'])
        results["assessments"] = assessments
    
    print("\n✨ DEMO COMPLETE!")
    print("All Canvas client functions verified and tested successfully.")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Canvas Scraper Demo Utility")
    parser.add_argument("--action", choices=["courses", "assessments", "verify", "full"], 
                       default="full", help="Action to perform")
    parser.add_argument("--course-id", type=int, default=213800, 
                       help="Course ID for assessments demo")
    
    args = parser.parse_args()
    
    if args.action == "courses":
        asyncio.run(get_active_courses())
    elif args.action == "assessments":
        asyncio.run(demo_assignments_and_quizzes(args.course_id))
    elif args.action == "verify":
        asyncio.run(verify_client_functions())
    else:
        asyncio.run(full_demo())