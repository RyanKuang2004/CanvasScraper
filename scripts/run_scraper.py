#!/usr/bin/env python3
"""
Simple Canvas Scraper Runner

A lightweight deployment script for running the Canvas scraper with logging and error handling.
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def setup_logging():
    """Set up logging configuration."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def main():
    """Main runner function."""
    logger = setup_logging()
    
    try:
        logger.info("Starting Canvas scraper...")
        
        # Import and run the Canvas client
        from canvas_client import CanvasClient
        import asyncio
        
        async def run_scraper():
            client = CanvasClient()
            # Add your scraping logic here
            logger.info("Canvas scraper completed successfully")
        
        asyncio.run(run_scraper())
        
    except Exception as e:
        logger.error(f"Canvas scraper failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()