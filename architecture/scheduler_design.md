# Scheduling & Orchestration Architecture

## Overview

The Scheduling & Orchestration system manages automated, reliable, and scalable execution of Canvas sync operations with intelligent resource management, error recovery, and adaptive scheduling capabilities.

## Core Components

### 1. Job Scheduler Architecture

**Technology Stack:**
- **Primary**: APScheduler with PostgreSQL job store for persistence
- **Queue System**: Celery with Redis for distributed task processing
- **Orchestration**: Docker Compose/Kubernetes for container management
- **Monitoring**: Prometheus + Grafana for observability

**Scheduler Design Pattern:**
```python
class CanvasScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(
            jobstores={
                'default': SqlAlchemyJobStore(
                    url='postgresql://canvas_scraper:password@localhost/canvas_db'
                )
            },
            executors={
                'default': AsyncIOExecutor(max_workers=10),
                'sync_executor': AsyncIOExecutor(max_workers=5)
            },
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutes
            }
        )
```

### 2. Adaptive Scheduling Algorithm

**Dynamic Interval Calculation:**
```python
class AdaptiveScheduler:
    def __init__(self):
        self.base_intervals = {
            'high_activity': timedelta(minutes=30),
            'normal_activity': timedelta(hours=1), 
            'low_activity': timedelta(hours=2),
            'inactive': timedelta(hours=6)
        }
        
    async def calculate_next_sync(self, course_id: int) -> datetime:
        course_activity = await self._analyze_course_activity(course_id)
        sync_history = await self._get_sync_history(course_id)
        
        # Activity-based scheduling
        base_interval = self.base_intervals[course_activity.level]
        
        # Adjust based on recent changes
        if course_activity.recent_change_rate > 0.2:
            interval = base_interval * 0.5  # More frequent for active courses
        elif course_activity.recent_change_rate < 0.05:
            interval = base_interval * 1.5  # Less frequent for stable courses
        else:
            interval = base_interval
            
        # Error rate adjustments
        if sync_history.recent_failures > 3:
            interval = min(interval * 2, timedelta(hours=6))  # Back off on failures
            
        # Time-of-day optimization
        next_time = datetime.utcnow() + interval
        return self._optimize_for_low_usage_hours(next_time)
    
    def _optimize_for_low_usage_hours(self, scheduled_time: datetime) -> datetime:
        """Shift sync times to low-usage hours when possible."""
        hour = scheduled_time.hour
        
        # Prefer scheduling during off-peak hours (2-6 AM local time)
        if 8 <= hour <= 22:  # Peak hours
            # Shift to next available off-peak window
            off_peak_time = scheduled_time.replace(hour=3, minute=0, second=0)
            if off_peak_time <= scheduled_time:
                off_peak_time += timedelta(days=1)
            return off_peak_time
            
        return scheduled_time
```

### 3. Job Queue Architecture

**Multi-tier Queue System:**
```python
class JobQueue:
    def __init__(self):
        self.queues = {
            'critical': Queue(priority=10, max_workers=3),    # Real-time updates
            'normal': Queue(priority=5, max_workers=5),       # Regular syncs
            'batch': Queue(priority=1, max_workers=2),        # Large batch operations
            'maintenance': Queue(priority=0, max_workers=1)   # Cleanup, optimization
        }
        
    async def enqueue_sync_job(self, job: SyncJob) -> JobHandle:
        """Enqueue a sync job in the appropriate queue based on priority."""
        
        queue_name = self._determine_queue(job)
        
        job_handle = JobHandle(
            id=uuid.uuid4(),
            job=job,
            queue=queue_name,
            created_at=datetime.utcnow(),
            estimated_duration=self._estimate_duration(job)
        )
        
        await self.queues[queue_name].put(job_handle)
        
        # Update job tracking in database
        await self._track_job(job_handle)
        
        return job_handle
    
    def _determine_queue(self, job: SyncJob) -> str:
        """Intelligent queue selection based on job characteristics."""
        if job.priority == JobPriority.CRITICAL:
            return 'critical'
        elif job.estimated_duration > timedelta(hours=1):
            return 'batch'
        elif job.job_type in ['maintenance', 'cleanup']:
            return 'maintenance'
        else:
            return 'normal'
```

### 4. Worker Management

**Auto-scaling Worker Pool:**
```python
class WorkerPool:
    def __init__(self):
        self.min_workers = 2
        self.max_workers = 10
        self.current_workers = self.min_workers
        self.worker_processes = {}
        
    async def manage_worker_scaling(self):
        """Dynamically scale workers based on queue depth and system load."""
        
        queue_metrics = await self._get_queue_metrics()
        system_metrics = await self._get_system_metrics()
        
        # Calculate desired worker count
        desired_workers = self._calculate_desired_workers(queue_metrics, system_metrics)
        
        if desired_workers > self.current_workers:
            await self._scale_up(desired_workers - self.current_workers)
        elif desired_workers < self.current_workers:
            await self._scale_down(self.current_workers - desired_workers)
    
    def _calculate_desired_workers(self, queue_metrics: QueueMetrics, 
                                 system_metrics: SystemMetrics) -> int:
        """Calculate optimal worker count based on current conditions."""
        
        # Base calculation on queue depth
        total_queued = sum(queue_metrics.depths.values())
        base_workers = min(math.ceil(total_queued / 5), self.max_workers)
        
        # Adjust for system load
        if system_metrics.cpu_usage > 80:
            base_workers = max(base_workers - 1, self.min_workers)
        elif system_metrics.cpu_usage < 40 and total_queued > 0:
            base_workers = min(base_workers + 1, self.max_workers)
            
        return max(self.min_workers, min(base_workers, self.max_workers))
```

### 5. Orchestration Engine

**Job Coordination and Dependencies:**
```python
class JobOrchestrator:
    def __init__(self):
        self.dependency_graph = nx.DiGraph()
        self.running_jobs = {}
        self.job_locks = defaultdict(asyncio.Lock)
        
    async def orchestrate_sync_workflow(self, course_ids: List[int]) -> WorkflowResult:
        """Orchestrate complex sync workflows with dependencies."""
        
        workflow = SyncWorkflow(course_ids)
        
        # Phase 1: Metadata sync (parallel for all courses)
        metadata_jobs = [
            SyncJob(job_type='metadata_sync', course_id=cid) 
            for cid in course_ids
        ]
        metadata_results = await self._execute_parallel(metadata_jobs)
        
        # Phase 2: Content extraction (parallel within courses, sequential between phases)
        extraction_jobs = []
        for course_id in course_ids:
            if metadata_results[course_id].success:
                extraction_jobs.append(
                    SyncJob(job_type='content_extraction', course_id=course_id)
                )
        
        extraction_results = await self._execute_parallel(extraction_jobs)
        
        # Phase 3: Search index update (sequential to avoid conflicts)
        index_jobs = [
            SyncJob(job_type='index_update', course_id=cid)
            for cid in course_ids
            if extraction_results.get(cid, {}).get('success', False)
        ]
        index_results = await self._execute_sequential(index_jobs)
        
        return WorkflowResult(
            metadata_results=metadata_results,
            extraction_results=extraction_results,
            index_results=index_results
        )
    
    async def _execute_with_dependencies(self, job: SyncJob) -> JobResult:
        """Execute job while respecting dependencies and resource locks."""
        
        # Wait for dependencies
        dependencies = self.dependency_graph.predecessors(job.id)
        for dep_id in dependencies:
            await self._wait_for_job_completion(dep_id)
        
        # Acquire necessary locks
        async with self.job_locks[job.resource_key]:
            return await self._execute_job(job)
```

## Hourly Sync Implementation

### Cron-style Scheduling Configuration

```python
class HourlySyncScheduler:
    def __init__(self):
        self.scheduler = CanvasScheduler()
        
    async def setup_hourly_syncs(self):
        """Configure hourly sync jobs for all active courses."""
        
        active_courses = await self._get_active_courses()
        
        for course in active_courses:
            # Stagger sync times to distribute load
            minute_offset = hash(course.id) % 60
            
            self.scheduler.add_job(
                func=self._perform_incremental_sync,
                trigger='cron',
                minute=minute_offset,
                args=[course.id],
                id=f'hourly_sync_{course.id}',
                name=f'Hourly sync for {course.name}',
                misfire_grace_time=900,  # 15 minutes grace
                coalesce=True,
                max_instances=1,
                replace_existing=True
            )
    
    async def _perform_incremental_sync(self, course_id: int):
        """Main hourly sync execution logic."""
        
        sync_job = SyncJob(
            job_type='incremental_sync',
            course_id=course_id,
            priority=JobPriority.NORMAL,
            scheduled_at=datetime.utcnow()
        )
        
        try:
            # Check if previous sync is still running
            if await self._is_sync_running(course_id):
                logger.warning(f"Skipping sync for course {course_id} - previous sync still running")
                return
            
            # Perform the sync
            result = await self.sync_engine.perform_incremental_sync(course_id)
            
            # Update scheduling based on result
            await self._adjust_schedule_based_on_result(course_id, result)
            
        except Exception as e:
            await self._handle_sync_error(course_id, e)
```

### Load Balancing and Resource Management

```python
class ResourceManager:
    def __init__(self):
        self.max_concurrent_syncs = 5
        self.max_api_calls_per_minute = 100
        self.current_api_calls = 0
        self.api_call_window_start = datetime.utcnow()
        
    async def acquire_sync_slot(self, course_id: int) -> Optional[SyncSlot]:
        """Acquire a sync slot with rate limiting and resource management."""
        
        # Check concurrent sync limit
        active_syncs = await self._count_active_syncs()
        if active_syncs >= self.max_concurrent_syncs:
            return None
        
        # Check API rate limit
        if not await self._check_api_rate_limit():
            return None
        
        # Acquire slot
        slot = SyncSlot(
            course_id=course_id,
            acquired_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=2)
        )
        
        await self._register_sync_slot(slot)
        return slot
    
    async def _check_api_rate_limit(self) -> bool:
        """Implement sliding window rate limiting for API calls."""
        now = datetime.utcnow()
        
        # Reset window if needed
        if (now - self.api_call_window_start).total_seconds() >= 60:
            self.current_api_calls = 0
            self.api_call_window_start = now
        
        return self.current_api_calls < self.max_api_calls_per_minute
```

## Monitoring and Health Management

### Job Health Monitoring

```python
class JobHealthMonitor:
    def __init__(self):
        self.health_checks = [
            self._check_scheduler_health,
            self._check_queue_health,
            self._check_worker_health,
            self._check_job_completion_rates
        ]
    
    async def monitor_job_health(self) -> HealthReport:
        """Comprehensive health monitoring for the job system."""
        
        health_results = []
        
        for health_check in self.health_checks:
            try:
                result = await health_check()
                health_results.append(result)
            except Exception as e:
                health_results.append(HealthCheckResult.failed(health_check.__name__, str(e)))
        
        overall_health = self._calculate_overall_health(health_results)
        
        return HealthReport(
            overall_health=overall_health,
            check_results=health_results,
            timestamp=datetime.utcnow()
        )
    
    async def _check_scheduler_health(self) -> HealthCheckResult:
        """Check if scheduler is running and responsive."""
        try:
            # Check if scheduler is running
            if not self.scheduler.running:
                return HealthCheckResult.failed("scheduler_running", "Scheduler is not running")
            
            # Check job store connectivity
            job_count = len(self.scheduler.get_jobs())
            
            return HealthCheckResult.success("scheduler_health", {
                "running": True,
                "job_count": job_count
            })
        except Exception as e:
            return HealthCheckResult.failed("scheduler_health", str(e))
```

### Alerting and Notifications

```python
class AlertManager:
    def __init__(self):
        self.alert_channels = [
            EmailAlertChannel(),
            SlackAlertChannel(), 
            PagerDutyAlertChannel()
        ]
        
    async def handle_sync_failure(self, course_id: int, error: Exception, 
                                failure_count: int):
        """Handle sync failures with escalating alerts."""
        
        alert_level = self._determine_alert_level(failure_count, error)
        
        alert = Alert(
            level=alert_level,
            title=f"Canvas Sync Failure - Course {course_id}",
            message=f"Sync failed {failure_count} times. Latest error: {str(error)}",
            metadata={
                "course_id": course_id,
                "error_type": type(error).__name__,
                "failure_count": failure_count,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Send alerts based on severity
        if alert_level >= AlertLevel.WARNING:
            await self._send_alert(alert, channels=['email'])
        if alert_level >= AlertLevel.CRITICAL:
            await self._send_alert(alert, channels=['email', 'slack', 'pagerduty'])
```

## Implementation Configuration

### Docker Compose Orchestration

```yaml
version: '3.8'

services:
  canvas-scheduler:
    build: .
    command: python -m schedulers.main
    environment:
      - SCHEDULER_MODE=primary
      - POSTGRES_URL=postgresql://user:pass@postgres:5432/canvas_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    
  canvas-worker:
    build: .
    command: python -m workers.main
    environment:
      - WORKER_TYPE=sync_worker
      - POSTGRES_URL=postgresql://user:pass@postgres:5432/canvas_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 3
    restart: unless-stopped
    
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: canvas_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
      
  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

This orchestration architecture ensures reliable, scalable, and efficient automated synchronization with comprehensive error handling, monitoring, and resource management.