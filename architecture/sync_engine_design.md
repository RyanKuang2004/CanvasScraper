# Incremental Sync Engine Architecture

## Overview

The Incremental Sync Engine ensures efficient, reliable, and intelligent synchronization of Canvas content with minimal API calls and processing overhead. It implements sophisticated change detection, deduplication, and error recovery mechanisms.

## Core Design Principles

### 1. Intelligent Change Detection
**Multi-layered approach to identify what needs updating:**

```python
# Change Detection Strategy
class ChangeDetectionStrategy:
    def detect_changes(self, entity_type, remote_data, local_data):
        # 1. Timestamp comparison (fastest)
        if self._timestamp_changed(remote_data, local_data):
            return ChangeType.TIMESTAMP_UPDATED
            
        # 2. Content hash comparison (medium cost)
        if self._content_hash_changed(remote_data, local_data):
            return ChangeType.CONTENT_UPDATED
            
        # 3. Deep content analysis (slowest, most accurate)
        if self._deep_content_changed(remote_data, local_data):
            return ChangeType.CONTENT_MODIFIED
            
        return ChangeType.NO_CHANGE
```

### 2. Deduplication Strategy
**Multi-tier deduplication to prevent unnecessary processing:**

```
Tier 1: Database Constraints (UNIQUE indexes)
   ↓
Tier 2: Content Hash Comparison (SHA-256)
   ↓  
Tier 3: Semantic Content Analysis (text similarity)
   ↓
Tier 4: Manual Conflict Resolution (logging + alerts)
```

## Sync Engine Components

### 1. Change Detection Engine

**API Metadata Analysis:**
```python
class MetadataChangeDetector:
    async def detect_api_changes(self, course_id: int, last_sync: datetime) -> List[Change]:
        # Fetch only items modified since last sync
        modified_items = await self.canvas_client.get_modified_since(
            course_id, 
            since=last_sync,
            include=['modules', 'module_items', 'files', 'pages']
        )
        
        changes = []
        for item in modified_items:
            change_type = self._determine_change_type(item)
            changes.append(Change(
                entity_type=item['type'],
                entity_id=item['id'],
                change_type=change_type,
                timestamp=item['updated_at'],
                metadata=item
            ))
        
        return changes
```

**Content Hash Tracking:**
```python
class ContentHashTracker:
    def calculate_content_hash(self, content: Any) -> str:
        """Calculate SHA-256 hash of content for change detection."""
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        elif isinstance(content, dict):
            # Normalize dict for consistent hashing
            normalized = json.dumps(content, sort_keys=True, separators=(',', ':'))
            content_bytes = normalized.encode('utf-8')
        else:
            content_bytes = str(content).encode('utf-8')
            
        return hashlib.sha256(content_bytes).hexdigest()
    
    async def has_content_changed(self, entity_id: str, new_content: Any) -> bool:
        """Check if content has changed since last sync."""
        new_hash = self.calculate_content_hash(new_content)
        stored_hash = await self.db.get_content_hash(entity_id)
        return new_hash != stored_hash
```

### 2. Intelligent Sync Scheduler

**Adaptive Scheduling Algorithm:**
```python
class AdaptiveSyncScheduler:
    def __init__(self):
        self.base_interval = timedelta(hours=1)  # Default hourly sync
        self.max_interval = timedelta(hours=6)   # Maximum interval
        self.min_interval = timedelta(minutes=15) # Minimum interval
        
    def calculate_next_sync(self, course_id: int) -> datetime:
        sync_state = await self.get_sync_state(course_id)
        
        # Adaptive interval based on:
        # 1. Change frequency
        # 2. Course activity level  
        # 3. Error rate
        # 4. Time of day/week patterns
        
        if sync_state.consecutive_failures > 3:
            # Back off exponentially for failing courses
            interval = min(
                self.base_interval * (2 ** sync_state.consecutive_failures),
                self.max_interval
            )
        elif sync_state.recent_change_rate > 0.1:  # >10% content changed recently
            # More frequent sync for active courses
            interval = max(self.base_interval / 2, self.min_interval)
        else:
            # Standard interval
            interval = self.base_interval
            
        return datetime.utcnow() + interval
```

### 3. Deduplication Engine

**Multi-tier Deduplication System:**

```python
class DeduplicationEngine:
    async def process_item(self, item: ContentItem) -> ProcessingResult:
        # Tier 1: Database constraint check
        if await self._exists_in_database(item):
            return ProcessingResult.DUPLICATE_SKIPPED
            
        # Tier 2: Content hash comparison
        content_hash = self._calculate_hash(item.content)
        if await self._hash_exists(content_hash):
            existing_item = await self._get_item_by_hash(content_hash)
            return await self._handle_hash_collision(item, existing_item)
            
        # Tier 3: Semantic similarity check
        if await self._has_similar_content(item):
            similar_items = await self._get_similar_content(item)
            return await self._resolve_similarity_conflict(item, similar_items)
            
        # Tier 4: New unique content
        return ProcessingResult.PROCESS_NEW
    
    async def _has_similar_content(self, item: ContentItem) -> bool:
        """Use text similarity algorithms to detect near-duplicates."""
        if not item.extracted_text:
            return False
            
        # Use PostgreSQL similarity functions or external service
        similar_items = await self.db.execute("""
            SELECT id, similarity(extracted_text, $1) as sim_score
            FROM content_extractions 
            WHERE course_id = $2 
            AND similarity(extracted_text, $1) > 0.8
            ORDER BY sim_score DESC
            LIMIT 5
        """, item.extracted_text, item.course_id)
        
        return len(similar_items) > 0
```

### 4. Error Recovery & Resilience

**Comprehensive Error Handling:**

```python
class SyncErrorHandler:
    def __init__(self):
        self.max_retries = 3
        self.backoff_multiplier = 2
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=300  # 5 minutes
        )
    
    async def handle_sync_error(self, error: Exception, context: SyncContext) -> ErrorAction:
        """Intelligent error handling with categorization and recovery."""
        
        error_category = self._categorize_error(error)
        
        if error_category == ErrorCategory.RATE_LIMIT:
            # Implement exponential backoff
            wait_time = self._calculate_backoff(context.retry_count)
            await asyncio.sleep(wait_time)
            return ErrorAction.RETRY
            
        elif error_category == ErrorCategory.NETWORK_TIMEOUT:
            # Network issues - retry with longer timeout
            context.timeout *= 1.5
            return ErrorAction.RETRY
            
        elif error_category == ErrorCategory.AUTHENTICATION:
            # Auth issues - alert and stop
            await self._send_alert("Authentication failed", context)
            return ErrorAction.STOP
            
        elif error_category == ErrorCategory.CONTENT_ERROR:
            # Content processing error - skip item but continue
            await self._log_content_error(error, context)
            return ErrorAction.SKIP_ITEM
            
        else:
            # Unknown error - log and retry with caution
            await self._log_unknown_error(error, context)
            return ErrorAction.RETRY_WITH_CAUTION
```

## Sync Workflow Architecture

### Complete Sync Flow

```
1. Sync Job Initialization
   ├── Determine sync type (full/incremental)
   ├── Load course sync state
   ├── Calculate change detection parameters
   └── Initialize error tracking

2. Change Detection Phase
   ├── Fetch Canvas API metadata
   ├── Compare with local timestamps
   ├── Identify modified entities
   └── Prioritize changes by importance

3. Content Processing Phase
   ├── Download modified content
   ├── Extract text content
   ├── Calculate content hashes
   └── Apply deduplication rules

4. Database Update Phase
   ├── Begin transaction
   ├── Update entity metadata
   ├── Insert/update extracted content
   ├── Update sync state
   └── Commit transaction

5. Post-Processing Phase
   ├── Update search indices
   ├── Generate sync report
   ├── Schedule next sync
   └── Clean up temporary files
```

### Incremental Sync Algorithm

```python
class IncrementalSyncEngine:
    async def perform_incremental_sync(self, course_id: int) -> SyncResult:
        """Main incremental sync algorithm."""
        
        sync_job = await self._create_sync_job(course_id, 'incremental')
        
        try:
            # 1. Get last sync timestamp
            last_sync = await self._get_last_sync_time(course_id)
            
            # 2. Detect changes since last sync
            changes = await self._detect_changes(course_id, last_sync)
            
            if not changes:
                return SyncResult.NO_CHANGES
            
            # 3. Process changes in batches
            results = []
            for batch in self._batch_changes(changes, batch_size=50):
                batch_result = await self._process_change_batch(batch)
                results.append(batch_result)
                
                # Progressive commitment for large syncs
                if len(results) % 5 == 0:
                    await self._commit_progress(sync_job, results)
            
            # 4. Finalize sync
            await self._finalize_sync(sync_job, results)
            
            return SyncResult.SUCCESS
            
        except Exception as e:
            await self._handle_sync_failure(sync_job, e)
            raise
```

### Batch Processing Strategy

```python
class BatchProcessor:
    def __init__(self, batch_size: int = 50, max_concurrent: int = 5):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_changes_batch(self, changes: List[Change]) -> BatchResult:
        """Process a batch of changes with controlled concurrency."""
        
        async def process_single_change(change: Change) -> ChangeResult:
            async with self.semaphore:
                try:
                    return await self._process_change(change)
                except Exception as e:
                    return ChangeResult.failed(change, e)
        
        # Process batch concurrently
        tasks = [process_single_change(change) for change in changes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return BatchResult(
            total=len(changes),
            successful=[r for r in results if r.success],
            failed=[r for r in results if not r.success]
        )
```

## Performance Optimization

### Caching Strategy
```python
class SyncCache:
    def __init__(self):
        self.redis_client = redis.Redis()
        self.local_cache = TTLCache(maxsize=1000, ttl=300)  # 5 min local cache
    
    async def get_cached_content(self, key: str) -> Optional[Any]:
        # L1: Local memory cache (fastest)
        if key in self.local_cache:
            return self.local_cache[key]
        
        # L2: Redis cache (fast)
        cached = await self.redis_client.get(key)
        if cached:
            value = json.loads(cached)
            self.local_cache[key] = value
            return value
        
        return None
```

### Database Optimization
```sql
-- Optimized queries for sync operations
CREATE INDEX CONCURRENTLY idx_content_extractions_sync_check 
ON content_extractions (source_type, source_id, content_hash, updated_at);

CREATE INDEX CONCURRENTLY idx_sync_jobs_active 
ON sync_jobs (status, job_type, started_at) 
WHERE status IN ('pending', 'running');

-- Partitioning for large datasets
CREATE TABLE content_extractions_y2024m01 PARTITION OF content_extractions
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## Monitoring & Observability

### Sync Metrics
```python
class SyncMetrics:
    def __init__(self):
        self.metrics = {
            'sync_duration': histogram('sync_duration_seconds'),
            'items_processed': counter('items_processed_total'),
            'errors_count': counter('sync_errors_total'),
            'dedup_hits': counter('deduplication_hits_total'),
            'cache_hits': counter('cache_hits_total')
        }
    
    def record_sync_completion(self, duration: float, items: int, errors: int):
        self.metrics['sync_duration'].observe(duration)
        self.metrics['items_processed'].inc(items)
        self.metrics['errors_count'].inc(errors)
```

### Health Checks
```python
class SyncHealthChecker:
    async def check_sync_health(self) -> HealthStatus:
        # Check for stuck sync jobs
        stuck_jobs = await self.db.count_stuck_sync_jobs()
        
        # Check sync lag
        max_lag = await self.db.get_max_sync_lag()
        
        # Check error rates
        error_rate = await self.db.get_recent_error_rate()
        
        if stuck_jobs > 0 or max_lag > timedelta(hours=3) or error_rate > 0.1:
            return HealthStatus.UNHEALTHY
        elif max_lag > timedelta(hours=1.5) or error_rate > 0.05:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
```

This incremental sync design ensures efficient, reliable, and scalable synchronization while minimizing API load and preventing duplicate processing.