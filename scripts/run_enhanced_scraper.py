#!/usr/bin/env python3
"""
Enhanced Canvas Scraper Runner

Main entry point for the enhanced Canvas scraper with file processing,
chunking, deduplication, and Supabase integration.
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path
from typing import Optional
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from canvas_orchestrator import CanvasOrchestrator


class ScraperRunner:
    """Runner for the enhanced Canvas scraper"""
    
    def __init__(self):
        self.orchestrator: Optional[CanvasOrchestrator] = None
        self.shutdown_requested = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        
        if self.orchestrator:
            self.orchestrator.stop_scheduled_processing()
    
    async def run_once(self, force_reprocess: bool = False) -> dict:
        """Run scraper once and exit"""
        print("Starting Canvas content synchronization...")
        
        try:
            self.orchestrator = CanvasOrchestrator()
            
            # Check prerequisites
            if not self.orchestrator.supabase.is_available():
                print("⚠️  Warning: Supabase not available - data will not be stored persistently")
                print("   Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
            
            # Load configuration
            enabled_courses = await self.orchestrator.course_manager.get_enabled_courses()
            if not enabled_courses:
                print("❌ No courses enabled for processing")
                print("   Configure courses in config/courses.yml")
                return {'error': 'No courses configured'}
            
            print(f"📚 Processing {len(enabled_courses)} enabled courses")
            
            # Run synchronization
            stats = await self.orchestrator.run_full_sync(force_reprocess=force_reprocess)
            
            # Display results
            print("\n" + "="*60)
            print("📊 SYNCHRONIZATION RESULTS")
            print("="*60)
            print(f"✅ Courses processed: {stats['courses_processed']}")
            print(f"📄 Files processed: {stats['files_processed']}")
            print(f"🧩 Chunks created: {stats['chunks_created']}")
            print(f"⏱️  Total time: {stats['processing_time_ms']:,}ms")
            
            if stats['errors']:
                print(f"❌ Errors: {len(stats['errors'])}")
                for error in stats['errors'][:3]:  # Show first 3 errors
                    print(f"   • {error}")
                if len(stats['errors']) > 3:
                    print(f"   ... and {len(stats['errors']) - 3} more")
            
            return stats
            
        except Exception as e:
            print(f"❌ Synchronization failed: {e}")
            return {'error': str(e)}
    
    async def run_daemon(self):
        """Run scraper as daemon with scheduled processing"""
        print("Starting Canvas scraper in daemon mode...")
        
        try:
            self.orchestrator = CanvasOrchestrator()
            
            # Check prerequisites
            if not self.orchestrator.supabase.is_available():
                print("❌ Supabase not available - daemon mode requires persistent storage")
                return
            
            # Start scheduled processing
            self.orchestrator.start_scheduled_processing()
            print("🕐 Scheduled processing started (12pm and 8pm Melbourne time)")
            print("🏃 Daemon running... Press Ctrl+C to stop")
            
            # Run daemon loop
            while not self.shutdown_requested:
                await asyncio.sleep(60)  # Check every minute
                
                # Optional: Add health checks, metrics, etc.
            
        except Exception as e:
            print(f"❌ Daemon failed: {e}")
        finally:
            if self.orchestrator:
                self.orchestrator.stop_scheduled_processing()
    
    async def run_search(self, query: str, course_id: Optional[str] = None):
        """Test search functionality"""
        try:
            self.orchestrator = CanvasOrchestrator()
            
            if not self.orchestrator.supabase.is_available():
                print("❌ Search requires Supabase - set SUPABASE_URL and SUPABASE_ANON_KEY")
                return
            
            print(f"🔍 Searching for: '{query}'")
            if course_id:
                print(f"📚 In course: {course_id}")
            
            results = await self.orchestrator.search_content(query, course_id, limit=10)
            
            if not results:
                print("❌ No results found")
                return
            
            print(f"\n✅ Found {len(results)} results:")
            print("-" * 60)
            
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.get('section_title', 'No title')}")
                print(f"   📄 File: {Path(result.get('file_path', '')).name}")
                if result.get('page_number'):
                    print(f"   📖 Page: {result['page_number']}")
                print(f"   📝 Content: {result.get('content', '')[:200]}...")
                print()
                
        except Exception as e:
            print(f"❌ Search failed: {e}")
    
    async def run_stats(self, course_id: Optional[str] = None):
        """Show processing statistics"""
        try:
            self.orchestrator = CanvasOrchestrator()
            
            print("📊 Getting processing statistics...")
            stats = await self.orchestrator.get_course_statistics(course_id)
            
            print("\n" + "="*60)
            print("📈 PROCESSING STATISTICS")
            print("="*60)
            
            # Orchestrator stats
            if 'orchestrator_stats' in stats:
                orch_stats = stats['orchestrator_stats']
                print(f"🎯 Last run: {orch_stats.get('last_run', 'Never')}")
                print(f"📚 Courses: {orch_stats.get('courses_processed', 0)}")
                print(f"📄 Files: {orch_stats.get('files_processed', 0)}")
                print(f"🧩 Chunks: {orch_stats.get('chunks_created', 0)}")
                
                if orch_stats.get('errors'):
                    print(f"❌ Recent errors: {len(orch_stats['errors'])}")
            
            # Course-specific stats
            if 'supabase_stats' in stats:
                sb_stats = stats['supabase_stats']
                print(f"\n📊 Course '{sb_stats.get('course_name', 'Unknown')}':")
                print(f"   📄 Files: {sb_stats.get('file_count', 0)}")
                print(f"   🧩 Chunks: {sb_stats.get('chunk_count', 0)}")
                print(f"   🎯 Tokens: {sb_stats.get('total_tokens', 0):,}")
                print(f"   🕐 Updated: {sb_stats.get('last_updated', 'Unknown')}")
            
            # File processor stats
            if 'file_processor_stats' in stats:
                fp_stats = stats['file_processor_stats']
                print(f"\n🔧 File processor:")
                print(f"   📁 Storage: {fp_stats.get('storage_directory', 'Unknown')}")
                print(f"   📄 Extensions: {', '.join(fp_stats.get('supported_extensions', []))}")
                print(f"   🧩 Chunk size: {fp_stats.get('chunk_size', 0)}")
                
        except Exception as e:
            print(f"❌ Failed to get statistics: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Enhanced Canvas Content Scraper")
    parser.add_argument('command', choices=['run', 'daemon', 'search', 'stats'], 
                       help='Command to execute')
    parser.add_argument('--force', action='store_true', 
                       help='Force reprocessing of all files')
    parser.add_argument('--course-id', type=str, 
                       help='Course ID for filtering (search/stats)')
    parser.add_argument('--query', type=str, 
                       help='Search query (for search command)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce noise from libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Create runner
    runner = ScraperRunner()
    
    # Execute command
    try:
        if args.command == 'run':
            result = asyncio.run(runner.run_once(force_reprocess=args.force))
            if 'error' in result:
                sys.exit(1)
        
        elif args.command == 'daemon':
            asyncio.run(runner.run_daemon())
        
        elif args.command == 'search':
            if not args.query:
                print("❌ Search requires --query parameter")
                sys.exit(1)
            asyncio.run(runner.run_search(args.query, args.course_id))
        
        elif args.command == 'stats':
            asyncio.run(runner.run_stats(args.course_id))
        
    except KeyboardInterrupt:
        print("\n👋 Shutdown complete")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()