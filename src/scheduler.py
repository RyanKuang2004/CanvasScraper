#!/usr/bin/env python3
"""
Melbourne Timezone Scheduler

Handles scheduling Canvas scraping operations with Melbourne timezone awareness,
including daylight saving time transitions and configurable execution times.
"""

import asyncio
import logging
from datetime import datetime, time
from typing import List, Dict, Any, Callable, Optional
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import yaml
from pathlib import Path


class MelbourneScheduler:
    """Melbourne timezone-aware scheduler for Canvas scraping"""
    
    def __init__(self, config_path: Path = None):
        self.logger = logging.getLogger(__name__)
        self.melbourne_tz = pytz.timezone('Australia/Melbourne')
        self.scheduler = AsyncIOScheduler(timezone=self.melbourne_tz)
        
        # Configuration
        self.config_path = config_path or Path("config/courses.yml")
        self.config: Dict[str, Any] = {}
        
        # Job tracking
        self.active_jobs: Dict[str, Any] = {}
        self.job_history: List[Dict[str, Any]] = []
        
        # Callbacks
        self.scraping_callback: Optional[Callable] = None
        
        # Set up event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
    
    async def load_scheduling_config(self) -> bool:
        """Load scheduling configuration from YAML file"""
        try:
            if not self.config_path.exists():
                self.logger.warning(f"Config file not found: {self.config_path}, using defaults")
                self._set_default_config()
                return True
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                full_config = yaml.safe_load(file)
                self.config = full_config.get('scheduling', {})
            
            self.logger.info("Loaded scheduling configuration")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load scheduling config: {e}")
            self._set_default_config()
            return False
    
    def _set_default_config(self):
        """Set default scheduling configuration"""
        self.config = {
            'enabled': True,
            'timezone': 'Australia/Melbourne',
            'run_times': ['12:00', '20:00'],
            'skip_days': [],
            'skip_dates': []
        }
    
    def set_scraping_callback(self, callback: Callable):
        """Set the callback function to execute during scheduled runs"""
        self.scraping_callback = callback
        self.logger.info("Scraping callback registered")
    
    async def setup_scheduled_jobs(self) -> bool:
        """Set up scheduled scraping jobs based on configuration"""
        try:
            if not self.config.get('enabled', False):
                self.logger.info("Scheduling disabled in configuration")
                return True
            
            if not self.scraping_callback:
                self.logger.error("No scraping callback registered")
                return False
            
            # Clear existing jobs
            self.scheduler.remove_all_jobs()
            self.active_jobs.clear()
            
            run_times = self.config.get('run_times', ['12:00', '20:00'])
            skip_days = [day.lower() for day in self.config.get('skip_days', [])]
            
            # Convert skip_days to scheduler format
            day_mapping = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            skip_day_numbers = [day_mapping.get(day) for day in skip_days if day in day_mapping]
            
            # Create jobs for each run time
            for i, run_time in enumerate(run_times):
                try:
                    hour, minute = map(int, run_time.split(':'))
                    
                    # Create cron trigger
                    # If skip_days specified, exclude them
                    if skip_day_numbers:
                        # Include all days except skip_days
                        allowed_days = [d for d in range(7) if d not in skip_day_numbers]
                        day_of_week = ','.join(map(str, allowed_days))
                    else:
                        day_of_week = '*'  # All days
                    
                    trigger = CronTrigger(
                        hour=hour,
                        minute=minute,
                        day_of_week=day_of_week,
                        timezone=self.melbourne_tz
                    )
                    
                    job_id = f'canvas_scrape_{i}_{hour:02d}{minute:02d}'
                    
                    job = self.scheduler.add_job(
                        self._execute_scraping_job,
                        trigger=trigger,
                        id=job_id,
                        name=f'Canvas Scraping - {run_time} Melbourne Time',
                        replace_existing=True,
                        max_instances=1  # Prevent overlapping executions
                    )
                    
                    self.active_jobs[job_id] = {
                        'time': run_time,
                        'trigger': trigger,
                        'job': job
                    }
                    
                    self.logger.info(f"Scheduled Canvas scraping for {run_time} Melbourne time (Job ID: {job_id})")
                    
                except ValueError as e:
                    self.logger.error(f"Invalid time format '{run_time}': {e}")
                    continue
            
            self.logger.info(f"Set up {len(self.active_jobs)} scheduled jobs")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup scheduled jobs: {e}")
            return False
    
    async def start_scheduler(self) -> bool:
        """Start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Melbourne scheduler started")
                
                # Log next run times
                for job_id, job_info in self.active_jobs.items():
                    next_run = job_info['job'].next_run_time
                    if next_run:
                        melbourne_time = next_run.astimezone(self.melbourne_tz)
                        self.logger.info(f"Next run for {job_id}: {melbourne_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                
                return True
            else:
                self.logger.warning("Scheduler already running")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
            return False
    
    async def stop_scheduler(self) -> bool:
        """Stop the scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                self.logger.info("Melbourne scheduler stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop scheduler: {e}")
            return False
    
    async def run_immediate_job(self) -> bool:
        """Run a scraping job immediately (outside of schedule)"""
        try:
            self.logger.info("Running immediate Canvas scraping job")
            await self._execute_scraping_job(immediate=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to run immediate job: {e}")
            return False
    
    async def _execute_scraping_job(self, immediate: bool = False):
        """Execute the actual scraping job"""
        job_start_time = datetime.now(self.melbourne_tz)
        job_type = "immediate" if immediate else "scheduled"
        
        try:
            self.logger.info(f"Starting {job_type} Canvas scraping job at {job_start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Check if we should skip today
            if not immediate and self._should_skip_today():
                self.logger.info("Skipping scraping job due to configuration (holiday/skip date)")
                return
            
            # Execute the scraping callback
            if self.scraping_callback:
                await self.scraping_callback()
                
                job_end_time = datetime.now(self.melbourne_tz)
                duration = job_end_time - job_start_time
                
                self.logger.info(f"Completed {job_type} Canvas scraping job in {duration.total_seconds():.1f} seconds")
                
                # Record job history
                self.job_history.append({
                    'type': job_type,
                    'start_time': job_start_time,
                    'end_time': job_end_time,
                    'duration_seconds': duration.total_seconds(),
                    'status': 'completed'
                })
                
                # Keep only last 50 job records
                if len(self.job_history) > 50:
                    self.job_history = self.job_history[-50:]
            else:
                self.logger.error("No scraping callback registered")
                
        except Exception as e:
            job_end_time = datetime.now(self.melbourne_tz)
            duration = job_end_time - job_start_time
            
            self.logger.error(f"Canvas scraping job failed after {duration.total_seconds():.1f} seconds: {e}")
            
            # Record failed job
            self.job_history.append({
                'type': job_type,
                'start_time': job_start_time,
                'end_time': job_end_time,
                'duration_seconds': duration.total_seconds(),
                'status': 'failed',
                'error': str(e)
            })
    
    def _should_skip_today(self) -> bool:
        """Check if today should be skipped based on configuration"""
        today = datetime.now(self.melbourne_tz).date()
        
        # Check skip_dates
        skip_dates = self.config.get('skip_dates', [])
        today_str = today.isoformat()
        
        if today_str in skip_dates:
            return True
        
        # Check skip_days (handled in cron trigger setup)
        # This is an additional check
        skip_days = [day.lower() for day in self.config.get('skip_days', [])]
        today_day_name = today.strftime('%A').lower()
        
        return today_day_name in skip_days
    
    def _job_executed(self, event):
        """Handle job execution events"""
        job_id = event.job_id
        self.logger.debug(f"Job {job_id} executed successfully")
    
    def _job_error(self, event):
        """Handle job error events"""
        job_id = event.job_id
        exception = event.exception
        self.logger.error(f"Job {job_id} failed with exception: {exception}")
    
    def get_next_run_times(self) -> Dict[str, str]:
        """Get next run times for all scheduled jobs"""
        next_runs = {}
        
        for job_id, job_info in self.active_jobs.items():
            next_run = job_info['job'].next_run_time
            if next_run:
                melbourne_time = next_run.astimezone(self.melbourne_tz)
                next_runs[job_id] = melbourne_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                next_runs[job_id] = "Not scheduled"
        
        return next_runs
    
    def get_job_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent job execution history"""
        return self.job_history[-limit:] if self.job_history else []
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status"""
        return {
            'running': self.scheduler.running,
            'timezone': str(self.melbourne_tz),
            'current_time': datetime.now(self.melbourne_tz).strftime('%Y-%m-%d %H:%M:%S %Z'),
            'active_jobs': len(self.active_jobs),
            'next_run_times': self.get_next_run_times(),
            'recent_jobs': self.get_job_history(5),
            'config': self.config
        }
    
    async def add_one_time_job(self, run_at: datetime, job_id: str = None) -> str:
        """
        Add a one-time job to run at a specific datetime
        
        Args:
            run_at: Melbourne time to run the job
            job_id: Optional job ID (auto-generated if not provided)
            
        Returns:
            Job ID of the created job
        """
        try:
            # Ensure run_at is in Melbourne timezone
            if run_at.tzinfo is None:
                run_at = self.melbourne_tz.localize(run_at)
            else:
                run_at = run_at.astimezone(self.melbourne_tz)
            
            if not job_id:
                job_id = f"onetime_{int(run_at.timestamp())}"
            
            job = self.scheduler.add_job(
                self._execute_scraping_job,
                trigger=DateTrigger(run_date=run_at),
                id=job_id,
                name=f"One-time Canvas Scraping - {run_at.strftime('%Y-%m-%d %H:%M')}",
                replace_existing=True,
                args=[True]  # immediate=True
            )
            
            self.logger.info(f"Added one-time job {job_id} for {run_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Failed to add one-time job: {e}")
            raise


async def main():
    """Test the Melbourne scheduler"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Mock scraping function
    async def mock_scraping_job():
        logger = logging.getLogger("MockScraper")
        logger.info("Mock scraping job started")
        await asyncio.sleep(2)  # Simulate work
        logger.info("Mock scraping job completed")
    
    # Create scheduler
    scheduler = MelbourneScheduler()
    
    # Set callback
    scheduler.set_scraping_callback(mock_scraping_job)
    
    # Load config
    await scheduler.load_scheduling_config()
    
    # Setup jobs
    await scheduler.setup_scheduled_jobs()
    
    # Start scheduler
    await scheduler.start_scheduler()
    
    # Show status
    status = scheduler.get_scheduler_status()
    print(f"Scheduler Status: {status}")
    
    # Run immediate job for testing
    print("Running immediate test job...")
    await scheduler.run_immediate_job()
    
    # Wait a bit then stop
    await asyncio.sleep(5)
    await scheduler.stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())