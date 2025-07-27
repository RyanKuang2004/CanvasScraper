#!/usr/bin/env python3
"""
Canvas API Demo Script

This script demonstrates the Canvas client by running specific functions
and printing their output in a formatted way.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List
import aiohttp

from canvas_client import CanvasClient, CanvasClientError


def print_json(data: Any, title: str) -> None:
    """Print data in a formatted JSON structure."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    if data:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("No data returned")
    print()


async def run_canvas_demo() -> None:
    """Run the Canvas client demo with the specified functions."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Starting Canvas API Demo...")
    
    try:
        # Initialize the Canvas client
        client = CanvasClient()
        
        async with aiohttp.ClientSession() as session:
            # 1. Get active courses
            print("\n🎓 Fetching active courses...")
            active_courses = await client.get_active_courses()
            print_json(active_courses, "ACTIVE COURSES")
            
            if not active_courses:
                print("No active courses found. Demo cannot continue.")
                return
            
            # Look for courses with different codes to test various item types
            courses_to_test = []
            
            # First priority: course with 90104 code
            for course in active_courses:
                course_name = course['name']
                if '90104' in course_name:
                    courses_to_test.append(course)
                    break
            
            # Add other courses with different codes for variety
            for course in active_courses:
                course_name = course['name']
                if any(code in course_name for code in ['COMP', 'SWEN', 'INFO', 'MAST']) and course not in courses_to_test:
                    courses_to_test.append(course)
                    if len(courses_to_test) >= 3:  # Test up to 3 courses
                        break
            
            # If no specific courses found, use first available
            if not courses_to_test:
                print("No courses with target codes found, using first available course")
                courses_to_test = [active_courses[0]]
            
            print(f"Testing {len(courses_to_test)} courses for module item analysis")
            
            for target_course in courses_to_test:
                course_id = target_course['id']
                course_name = target_course['name']
                
                print(f"\n{'='*80}")
                print(f"ANALYZING COURSE: {course_name} (ID: {course_id})")
                print(f"{'='*80}")
                
                # 2. Get due dates for the selected course
                print(f"\n📅 Fetching due dates for {course_name}...")
                due_dates = await client.get_due_dates(session, course_id)
                print_json(due_dates, f"DUE DATES FOR {course_name}")
                
                # 3. Get module items with ALL FIELDS for the selected course
                print(f"\n📚 Fetching modules and their items (ALL FIELDS) for {course_name}...")
                
                # First get modules
                modules = await client.get_modules(session, course_id)
                if modules:
                    print_json([{"id": m["id"], "name": m["name"]} for m in modules], 
                              f"MODULES IN {course_name}")
                    
                    # Get items for each module with ALL fields
                    items_by_type = {"File": [], "Page": [], "Assignment": [], "Quiz": [], "ExternalTool": [], "ExternalUrl": [], "SubHeader": [], "Other": []}
                    
                    for module in modules[:5]:  # Check first 5 modules for variety
                        module_id = module['id']
                        module_name = module['name']
                        
                        print(f"\n📖 Fetching ALL FIELDS for items in module: {module_name}")
                        module_items = await client.get_module_items(session, course_id, module_id)
                        
                        if module_items:
                            for item in module_items:
                                # Store the complete item with all fields
                                complete_item = {
                                    "course_name": course_name,
                                    "module_info": {
                                        "module_name": module_name,
                                        "module_id": module_id
                                    },
                                    "all_item_fields": item  # Store the entire item as-is
                                }
                                
                                item_type = item.get("type", "Other")
                                if item_type in items_by_type:
                                    items_by_type[item_type].append(complete_item)
                                else:
                                    items_by_type["Other"].append(complete_item)
                        else:
                            print(f"No items found in module: {module_name}")
                    
                    # Display items grouped by type with ALL fields
                    for item_type, items in items_by_type.items():
                        if items:
                            print_json(items[:2], f"ALL FIELDS FOR {item_type} ITEMS (showing first 2)")  # Limit to first 2 for readability
                            print(f"Found {len(items)} {item_type} items total")
                    
                    # Summary of item types found
                    summary = {item_type: len(items) for item_type, items in items_by_type.items() if items}
                    print_json(summary, f"SUMMARY: ITEM TYPES AND COUNTS FOR {course_name}")
                    
                else:
                    print(f"No modules found in course: {course_name}")
                
                print(f"\n{'='*80}")
                print(f"COMPLETED ANALYSIS FOR: {course_name}")
                print(f"{'='*80}")
    
    except CanvasClientError as e:
        print(f"❌ Canvas client error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise


def main() -> None:
    """Main entry point for the demo script."""
    asyncio.run(run_canvas_demo())


if __name__ == "__main__":
    main()