# Intermud3 Gateway Performance Tuning Guide

## Overview

This guide provides comprehensive performance optimization strategies for the Intermud3 Gateway. It covers system-level tuning, application optimization, network performance, monitoring, and scaling strategies for high-traffic scenarios.

**Current Status**: Phase 3 Complete (2025-08-20) - Achieving 1000+ msg/sec throughput with <100ms latency. Test coverage at 78% with 1200+ tests.

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [System-Level Optimization](#system-level-optimization)
3. [Gateway Configuration Tuning](#gateway-configuration-tuning)
4. [Network Optimization](#network-optimization)
5. [Application-Level Tuning](#application-level-tuning)
6. [Database and Storage Optimization](#database-and-storage-optimization)
7. [Monitoring and Metrics](#monitoring-and-metrics)
8. [Load Testing](#load-testing)
9. [Scaling Strategies](#scaling-strategies)
10. [Troubleshooting Performance Issues](#troubleshooting-performance-issues)

## Performance Targets

### Baseline Performance Goals

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Latency** | <50ms (p99) | Response time for API calls |
| **Event Distribution** | <30ms (p99) | Time to deliver events to clients |
| **Message Throughput** | 1000+ msg/sec | Sustained message processing (achieved) |
| **Concurrent Connections** | 1000+ | Active WebSocket connections |
| **Memory Usage** | <200MB | For 1000 concurrent clients |
| **CPU Usage** | <70% | Single core at peak load |
| **Network Throughput** | <10Mbps | For 1000 active clients |
| **Connection Setup** | <100ms | WebSocket handshake time |

### High-Performance Targets

| Metric | Target | Use Case |
|--------|--------|----------|
| **API Latency** | <25ms (p99) | High-frequency trading MUDs |
| **Event Distribution** | <15ms (p99) | Real-time chat applications |
| **Message Throughput** | 5000+ msg/sec | Large MUD networks |
| **Concurrent Connections** | 10000+ | Massive multiplayer events |
| **Memory Usage** | <1GB | For 10000 concurrent clients |

## System-Level Optimization

### Operating System Tuning

#### Linux Kernel Parameters

```bash
# /etc/sysctl.conf - Network performance tuning

# Increase network buffer sizes
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.rmem_default = 65536
net.core.wmem_default = 65536

# TCP buffer sizes
net.ipv4.tcp_rmem = 4096 65536 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# Increase connection tracking
net.netfilter.nf_conntrack_max = 1000000
net.core.netdev_max_backlog = 5000

# TCP optimization
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_tw_reuse = 1

# File descriptor limits
fs.file-max = 2097152

# Apply changes
sysctl -p
```

#### Process Limits

```bash
# /etc/security/limits.conf
* soft nofile 65536
* hard nofile 65536
* soft nproc 32768
* hard nproc 32768

# Verify limits
ulimit -n  # File descriptors
ulimit -u  # Processes
```

#### CPU Affinity and NUMA

```bash
# Check NUMA topology
numactl --hardware

# Run gateway on specific NUMA node
numactl --cpunodebind=0 --membind=0 python -m src -c config/config.yaml

# CPU affinity for specific cores
taskset -c 0-3 python -m src -c config/config.yaml
```

### Memory Management

#### Huge Pages Configuration

```bash
# Enable huge pages
echo 1024 > /proc/sys/vm/nr_hugepages

# Configure in /etc/sysctl.conf
vm.nr_hugepages = 1024
vm.hugetlb_shm_group = 1001  # Gateway group ID

# Mount huge pages
mkdir -p /mnt/huge
mount -t hugetlbfs nodev /mnt/huge
echo "/mnt/huge hugetlbfs defaults 0 0" >> /etc/fstab
```

#### Memory Allocation Tuning

```bash
# Reduce memory fragmentation
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag

# Swap configuration
echo 1 > /proc/sys/vm/swappiness  # Minimize swapping
```

### I/O Optimization

#### Disk I/O Scheduling

```bash
# Set I/O scheduler to deadline for SSDs
echo deadline > /sys/block/sda/queue/scheduler

# Or use noop for SSDs
echo noop > /sys/block/sda/queue/scheduler

# Increase read-ahead for logs
echo 4096 > /sys/block/sda/queue/read_ahead_kb
```

#### Log File Optimization

```yaml
# config/config.yaml - Optimized logging
logging:
  level: "INFO"  # Reduce log verbosity in production
  file: "/tmp/i3-gateway.log"  # Use tmpfs for logs
  async: true    # Enable async logging
  buffer_size: 65536
  batch_size: 100
  format: "json"  # Structured logging for performance
```

## Gateway Configuration Tuning

### Core Gateway Settings

```yaml
# config/performance.yaml
gateway:
  # Connection pool optimization
  max_connections: 1000
  connection_pool_size: 50
  keepalive_timeout: 300
  
  # Message processing
  queue_size: 10000
  worker_threads: 8  # Match CPU cores
  batch_size: 100
  batch_timeout: 10  # milliseconds
  
  # Memory management
  max_packet_size: 32768  # Reduce if memory constrained
  message_cache_size: 10000
  session_cache_size: 5000
  
  # Timeout optimization
  timeout: 15  # Reduce from default 30
  retry_attempts: 2  # Reduce retry attempts
  retry_delay: 1  # Faster retries

api:
  # WebSocket optimization (Port 8080)
  websocket:
    enabled: true
    host: "0.0.0.0"
    port: 8080
    max_connections: 5000
    ping_interval: 60  # Reduce ping frequency
    ping_timeout: 30
    max_frame_size: 65536
    compression: false  # Disable if CPU bound
    per_message_deflate: false
    
  # TCP optimization (Port 8081)
  tcp:
    enabled: true
    host: "0.0.0.0"
    port: 8081
    max_connections: 2000
    buffer_size: 65536  # Larger buffers
    nodelay: true  # Disable Nagle's algorithm
    keepalive: true
    
  # Session management
  session:
    timeout: 1800  # Reduce session timeout
    max_queue_size: 5000  # Larger message queues
    queue_ttl: 600
    cleanup_interval: 30  # More frequent cleanup
    batch_cleanup: true
    
  # Rate limiting optimization
  rate_limits:
    algorithm: "token_bucket"  # More efficient than sliding window
    default:
      per_minute: 1000
      burst: 200
    per_connection:
      enabled: true
      max_per_second: 50
```

### Memory Pool Configuration

```yaml
# Advanced memory management
gateway:
  memory_pools:
    packet_pool:
      initial_size: 1000
      max_size: 10000
      object_size: 4096
    
    session_pool:
      initial_size: 500
      max_size: 5000
      
    message_pool:
      initial_size: 2000
      max_size: 20000
      object_size: 1024
```

### Event System Optimization

```yaml
api:
  events:
    # Event processing
    worker_threads: 4
    queue_size: 50000
    batch_size: 500
    batch_timeout: 5
    
    # Event filtering
    enable_filtering: true
    filter_cache_size: 10000
    
    # Subscription management
    subscription_cache_size: 5000
    subscription_cleanup_interval: 300
```

## Network Optimization

### TCP Socket Tuning

```python
# src/api/optimized_server.py
import socket

def configure_socket(sock):
    """Apply socket optimizations."""
    # Disable Nagle's algorithm for low latency
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    
    # Enable keep-alive
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    # Reuse address
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Set buffer sizes
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    
    # Linux-specific optimizations
    if hasattr(socket, 'TCP_QUICKACK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)
```

### WebSocket Optimization

```python
# src/api/optimized_websocket.py
from aiohttp import web, WSMsgType
import ujson as json  # Faster JSON library

class OptimizedWebSocketHandler:
    def __init__(self):
        self.compression_threshold = 1024  # Only compress large messages
        self.message_pool = MessagePool(1000)
    
    async def handle_websocket(self, request):
        ws = web.WebSocketResponse(
            compress=False,  # Disable compression for speed
            max_msg_size=65536,
            timeout=30,
            autoping=False  # Manual ping control
        )
        
        await ws.prepare(request)
        
        # Optimize message handling
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                # Use fast JSON parser
                try:
                    data = json.loads(msg.data)
                    await self.process_message_fast(ws, data)
                except:
                    await ws.close(code=1003, message=b'Invalid JSON')
    
    async def process_message_fast(self, ws, data):
        """Optimized message processing."""
        # Pre-allocate response object
        response = self.message_pool.get()
        try:
            # Fast path for common messages
            if data.get("method") == "tell":
                await self.handle_tell_fast(data, response)
            elif data.get("method") == "channel_send":
                await self.handle_channel_fast(data, response)
            else:
                await self.handle_generic(data, response)
            
            # Send response
            if response:
                await ws.send_str(json.dumps(response))
        finally:
            self.message_pool.return_object(response)
```

### Connection Pooling

```python
# src/network/connection_pool.py
import asyncio
from collections import deque
import time

class OptimizedConnectionPool:
    def __init__(self, max_size=100, min_size=10):
        self.max_size = max_size
        self.min_size = min_size
        self.pool = deque()
        self.active_connections = set()
        self.stats = {
            'created': 0,
            'reused': 0,
            'destroyed': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }
    
    async def get_connection(self, host, port):
        """Get connection with optimized pooling."""
        # Try to reuse existing connection
        for _ in range(len(self.pool)):
            conn = self.pool.popleft()
            if self.is_connection_healthy(conn):
                self.active_connections.add(conn)
                self.stats['reused'] += 1
                self.stats['pool_hits'] += 1
                return conn
            else:
                await self.close_connection(conn)
        
        # Create new connection
        self.stats['pool_misses'] += 1
        conn = await self.create_optimized_connection(host, port)
        self.active_connections.add(conn)
        return conn
    
    async def create_optimized_connection(self, host, port):
        """Create optimized connection."""
        # Use optimized connection parameters
        reader, writer = await asyncio.open_connection(
            host, port,
            limit=65536,  # Larger buffer
            family=socket.AF_INET  # Force IPv4 for speed
        )
        
        # Configure socket
        sock = writer.get_extra_info('socket')
        if sock:
            configure_socket(sock)
        
        conn = Connection(reader, writer, time.time())
        self.stats['created'] += 1
        return conn
    
    async def return_connection(self, conn):
        """Return connection to pool."""
        if conn in self.active_connections:
            self.active_connections.remove(conn)
        
        if len(self.pool) < self.max_size and self.is_connection_healthy(conn):
            self.pool.append(conn)
        else:
            await self.close_connection(conn)
```

## Application-Level Tuning

### Message Processing Optimization

```python
# src/api/optimized_handlers.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
import ujson as json

class OptimizedMessageProcessor:
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=8)
        self.message_cache = {}  # LRU cache for frequent messages
        self.batch_processor = BatchProcessor()
    
    async def process_message(self, session, message):
        """Optimized message processing with batching."""
        message_type = message.get("method")
        
        # Fast path for high-frequency messages
        if message_type in ["tell", "channel_send"]:
            return await self.process_fast_path(session, message)
        
        # Batch processing for bulk operations
        elif message_type in ["who", "mudlist"]:
            return await self.batch_processor.add_request(session, message)
        
        # CPU-intensive operations in thread pool
        elif message_type in ["finger", "locate"]:
            return await asyncio.get_event_loop().run_in_executor(
                self.thread_pool, 
                self.process_cpu_intensive, 
                session, 
                message
            )
        
        return await self.process_generic(session, message)
    
    async def process_fast_path(self, session, message):
        """Optimized fast path for common operations."""
        # Pre-validate message structure
        if not self.quick_validate(message):
            return self.error_response(message.get("id"), "Invalid message")
        
        # Use object pooling for response
        response = ResponsePool.get()
        try:
            # Direct processing without excessive validation
            if message["method"] == "tell":
                await self.handle_tell_optimized(session, message, response)
            elif message["method"] == "channel_send":
                await self.handle_channel_optimized(session, message, response)
            
            return response
        finally:
            ResponsePool.return_object(response)

class BatchProcessor:
    """Batch similar requests for efficiency."""
    
    def __init__(self, batch_size=50, timeout=0.01):
        self.batch_size = batch_size
        self.timeout = timeout
        self.batches = {}
        self.timers = {}
    
    async def add_request(self, session, message):
        """Add request to batch."""
        batch_key = (message["method"], message.get("params", {}).get("target_mud"))
        
        if batch_key not in self.batches:
            self.batches[batch_key] = []
            # Set timeout for batch processing
            self.timers[batch_key] = asyncio.create_task(
                self.process_batch_after_timeout(batch_key)
            )
        
        self.batches[batch_key].append((session, message))
        
        # Process if batch is full
        if len(self.batches[batch_key]) >= self.batch_size:
            await self.process_batch(batch_key)
    
    async def process_batch(self, batch_key):
        """Process a batch of requests."""
        if batch_key not in self.batches:
            return
        
        batch = self.batches[batch_key]
        del self.batches[batch_key]
        
        # Cancel timeout
        if batch_key in self.timers:
            self.timers[batch_key].cancel()
            del self.timers[batch_key]
        
        # Process all requests in batch
        if batch_key[0] == "who":
            await self.process_who_batch(batch)
        elif batch_key[0] == "mudlist":
            await self.process_mudlist_batch(batch)
```

### Memory Optimization

```python
# src/utils/memory_management.py
import weakref
from collections import deque
import gc

class ObjectPool:
    """High-performance object pool."""
    
    def __init__(self, factory, initial_size=100, max_size=1000):
        self.factory = factory
        self.max_size = max_size
        self.pool = deque(maxlen=max_size)
        
        # Pre-allocate objects
        for _ in range(initial_size):
            self.pool.append(factory())
    
    def get(self):
        """Get object from pool."""
        if self.pool:
            return self.pool.popleft()
        return self.factory()
    
    def return_object(self, obj):
        """Return object to pool."""
        if len(self.pool) < self.max_size:
            # Reset object state
            if hasattr(obj, 'reset'):
                obj.reset()
            self.pool.append(obj)

class MemoryMonitor:
    """Monitor and optimize memory usage."""
    
    def __init__(self):
        self.last_gc = time.time()
        self.gc_threshold = 60  # seconds
        self.memory_threshold = 500 * 1024 * 1024  # 500MB
    
    async def periodic_cleanup(self):
        """Periodic memory cleanup."""
        while True:
            try:
                current_time = time.time()
                
                # Force garbage collection if needed
                if current_time - self.last_gc > self.gc_threshold:
                    collected = gc.collect()
                    self.last_gc = current_time
                    if collected > 0:
                        logger.debug(f"Garbage collected {collected} objects")
                
                # Check memory usage
                memory_usage = self.get_memory_usage()
                if memory_usage > self.memory_threshold:
                    await self.emergency_cleanup()
                
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Memory cleanup error: {e}")
    
    def get_memory_usage(self):
        """Get current memory usage."""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss
    
    async def emergency_cleanup(self):
        """Emergency memory cleanup."""
        # Clear caches
        for cache in [message_cache, session_cache, connection_cache]:
            cache.clear()
        
        # Force garbage collection
        gc.collect()
        
        logger.warning("Emergency memory cleanup performed")
```

### Async I/O Optimization

```python
# src/utils/async_optimization.py
import asyncio
import uvloop  # Faster event loop

class OptimizedAsyncManager:
    """Optimized async I/O management."""
    
    def __init__(self):
        # Use uvloop for better performance
        if hasattr(asyncio, 'set_event_loop_policy'):
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        
        self.semaphores = {}
        self.rate_limiters = {}
    
    def get_semaphore(self, name, limit):
        """Get named semaphore for resource limiting."""
        if name not in self.semaphores:
            self.semaphores[name] = asyncio.Semaphore(limit)
        return self.semaphores[name]
    
    async def gather_with_concurrency_limit(self, *tasks, limit=100):
        """Execute tasks with concurrency limit."""
        semaphore = asyncio.Semaphore(limit)
        
        async def sem_task(task):
            async with semaphore:
                return await task
        
        return await asyncio.gather(*[sem_task(task) for task in tasks])
    
    async def process_with_backpressure(self, queue, processor, max_workers=10):
        """Process queue with backpressure control."""
        semaphore = asyncio.Semaphore(max_workers)
        
        async def worker():
            while True:
                async with semaphore:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=1.0)
                        await processor(item)
                        queue.task_done()
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Worker error: {e}")
        
        # Start workers
        workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
        return workers
```

## Database and Storage Optimization

### Session Storage Optimization

```python
# src/state/optimized_storage.py
import asyncio
import pickle
import lz4  # Fast compression
from collections import OrderedDict

class OptimizedSessionStore:
    """High-performance session storage."""
    
    def __init__(self, max_memory_sessions=10000):
        self.memory_cache = OrderedDict()
        self.max_memory_sessions = max_memory_sessions
        self.disk_cache = {}
        self.compression_enabled = True
    
    async def store_session(self, session_id, session_data):
        """Store session with optimization."""
        # Serialize and compress
        if self.compression_enabled:
            data = lz4.compress(pickle.dumps(session_data))
        else:
            data = pickle.dumps(session_data)
        
        # Store in memory cache (LRU)
        if len(self.memory_cache) >= self.max_memory_sessions:
            # Remove oldest
            oldest_id, oldest_data = self.memory_cache.popitem(last=False)
            # Optionally persist to disk
            await self.persist_to_disk(oldest_id, oldest_data)
        
        self.memory_cache[session_id] = data
    
    async def get_session(self, session_id):
        """Get session with caching."""
        # Check memory cache first
        if session_id in self.memory_cache:
            # Move to end (mark as recently used)
            data = self.memory_cache.pop(session_id)
            self.memory_cache[session_id] = data
            
            # Deserialize
            if self.compression_enabled:
                return pickle.loads(lz4.decompress(data))
            else:
                return pickle.loads(data)
        
        # Check disk cache
        data = await self.load_from_disk(session_id)
        if data:
            # Add to memory cache
            await self.store_session(session_id, data)
            return data
        
        return None
```

### Message Queue Optimization

```python
# src/api/optimized_queue.py
import asyncio
from collections import deque
import heapq
import time

class OptimizedMessageQueue:
    """High-performance message queue with priorities."""
    
    def __init__(self, max_size=50000):
        self.max_size = max_size
        self.high_priority = deque()
        self.normal_priority = deque()
        self.low_priority = deque()
        self.delayed_messages = []  # Priority queue for delayed messages
        self.total_size = 0
        self.lock = asyncio.Lock()
    
    async def put(self, message, priority='normal', delay=0):
        """Add message to queue with priority and delay."""
        async with self.lock:
            current_time = time.time()
            
            if delay > 0:
                # Add to delayed queue
                heapq.heappush(
                    self.delayed_messages, 
                    (current_time + delay, priority, message)
                )
            else:
                # Add to appropriate priority queue
                if priority == 'high':
                    if len(self.high_priority) < self.max_size // 4:
                        self.high_priority.append(message)
                        self.total_size += 1
                elif priority == 'low':
                    if len(self.low_priority) < self.max_size // 4:
                        self.low_priority.append(message)
                        self.total_size += 1
                else:  # normal priority
                    if len(self.normal_priority) < self.max_size // 2:
                        self.normal_priority.append(message)
                        self.total_size += 1
            
            # Check for queue overflow
            if self.total_size > self.max_size:
                await self.handle_overflow()
    
    async def get(self):
        """Get message with priority ordering."""
        async with self.lock:
            # Process delayed messages
            await self.process_delayed_messages()
            
            # Get from highest priority queue first
            if self.high_priority:
                self.total_size -= 1
                return self.high_priority.popleft()
            elif self.normal_priority:
                self.total_size -= 1
                return self.normal_priority.popleft()
            elif self.low_priority:
                self.total_size -= 1
                return self.low_priority.popleft()
            
            return None
    
    async def process_delayed_messages(self):
        """Process delayed messages that are ready."""
        current_time = time.time()
        
        while (self.delayed_messages and 
               self.delayed_messages[0][0] <= current_time):
            _, priority, message = heapq.heappop(self.delayed_messages)
            
            # Add to appropriate queue
            if priority == 'high' and len(self.high_priority) < self.max_size // 4:
                self.high_priority.append(message)
                self.total_size += 1
            elif priority == 'normal' and len(self.normal_priority) < self.max_size // 2:
                self.normal_priority.append(message)
                self.total_size += 1
            elif priority == 'low' and len(self.low_priority) < self.max_size // 4:
                self.low_priority.append(message)
                self.total_size += 1
```

## Monitoring and Metrics

### Performance Metrics Collection

```python
# src/monitoring/performance_monitor.py
import time
import asyncio
from collections import defaultdict, deque
import psutil

class PerformanceMonitor:
    """Comprehensive performance monitoring."""
    
    def __init__(self, window_size=300):  # 5 minute windows
        self.window_size = window_size
        self.metrics = defaultdict(lambda: deque(maxlen=window_size))
        self.counters = defaultdict(int)
        self.timers = {}
        self.last_cleanup = time.time()
    
    def record_latency(self, operation, latency):
        """Record operation latency."""
        self.metrics[f"{operation}_latency"].append({
            'timestamp': time.time(),
            'value': latency
        })
    
    def increment_counter(self, counter_name):
        """Increment a counter."""
        self.counters[counter_name] += 1
    
    def start_timer(self, operation_id):
        """Start timing an operation."""
        self.timers[operation_id] = time.time()
    
    def end_timer(self, operation_id, operation_type):
        """End timing and record latency."""
        if operation_id in self.timers:
            latency = time.time() - self.timers[operation_id]
            self.record_latency(operation_type, latency)
            del self.timers[operation_id]
    
    def get_statistics(self):
        """Get performance statistics."""
        stats = {}
        current_time = time.time()
        
        # Calculate latency percentiles
        for metric_name, values in self.metrics.items():
            if values and metric_name.endswith('_latency'):
                # Filter recent values
                recent_values = [
                    v['value'] for v in values 
                    if current_time - v['timestamp'] < 60  # Last minute
                ]
                
                if recent_values:
                    recent_values.sort()
                    stats[metric_name] = {
                        'p50': self.percentile(recent_values, 50),
                        'p95': self.percentile(recent_values, 95),
                        'p99': self.percentile(recent_values, 99),
                        'avg': sum(recent_values) / len(recent_values),
                        'count': len(recent_values)
                    }
        
        # Add counter rates
        for counter_name, count in self.counters.items():
            stats[f"{counter_name}_rate"] = count / 60  # Per second
        
        # System metrics
        process = psutil.Process()
        stats['system'] = {
            'cpu_percent': process.cpu_percent(),
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'connections': len(process.connections()),
            'threads': process.num_threads(),
            'open_files': process.num_fds()
        }
        
        return stats
    
    def percentile(self, values, p):
        """Calculate percentile."""
        if not values:
            return 0
        k = (len(values) - 1) * p / 100
        f = int(k)
        c = k - f
        if f + 1 < len(values):
            return values[f] + c * (values[f + 1] - values[f])
        return values[f]
```

### Real-time Dashboard

```python
# src/monitoring/dashboard.py
from aiohttp import web
import json
import asyncio

class PerformanceDashboard:
    """Real-time performance dashboard."""
    
    def __init__(self, monitor):
        self.monitor = monitor
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup dashboard routes."""
        self.app.router.add_get('/dashboard', self.dashboard_page)
        self.app.router.add_get('/metrics/json', self.metrics_json)
        self.app.router.add_get('/metrics/prometheus', self.metrics_prometheus)
        self.app.router.add_static('/static/', 'monitoring/static/')
    
    async def dashboard_page(self, request):
        """Serve dashboard HTML."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>I3 Gateway Performance Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .metric-card { 
                    border: 1px solid #ddd; 
                    padding: 15px; 
                    margin: 10px; 
                    border-radius: 5px;
                    display: inline-block;
                    width: 200px;
                }
                .metric-value { 
                    font-size: 24px; 
                    font-weight: bold; 
                    color: #2196F3;
                }
                .chart-container { 
                    width: 400px; 
                    height: 200px; 
                    display: inline-block;
                    margin: 10px;
                }
            </style>
        </head>
        <body>
            <h1>I3 Gateway Performance Dashboard</h1>
            
            <div id="metrics-cards"></div>
            
            <div class="chart-container">
                <canvas id="latency-chart"></canvas>
            </div>
            
            <div class="chart-container">
                <canvas id="throughput-chart"></canvas>
            </div>
            
            <script>
                // Update metrics every second
                setInterval(updateMetrics, 1000);
                
                async function updateMetrics() {
                    try {
                        const response = await fetch('/metrics/json');
                        const metrics = await response.json();
                        updateMetricsCards(metrics);
                        updateCharts(metrics);
                    } catch (error) {
                        console.error('Failed to fetch metrics:', error);
                    }
                }
                
                function updateMetricsCards(metrics) {
                    const cardsContainer = document.getElementById('metrics-cards');
                    cardsContainer.innerHTML = '';
                    
                    // Key metrics to display
                    const keyMetrics = [
                        'api_latency_p99',
                        'tell_rate',
                        'channel_message_rate',
                        'active_connections',
                        'memory_mb',
                        'cpu_percent'
                    ];
                    
                    keyMetrics.forEach(metric => {
                        if (metrics[metric] !== undefined) {
                            const card = document.createElement('div');
                            card.className = 'metric-card';
                            card.innerHTML = `
                                <div>${metric.replace(/_/g, ' ').toUpperCase()}</div>
                                <div class="metric-value">${formatValue(metrics[metric])}</div>
                            `;
                            cardsContainer.appendChild(card);
                        }
                    });
                }
                
                function formatValue(value) {
                    if (typeof value === 'number') {
                        if (value < 1) {
                            return (value * 1000).toFixed(1) + 'ms';
                        } else if (value > 1000) {
                            return (value / 1000).toFixed(1) + 'k';
                        } else {
                            return value.toFixed(1);
                        }
                    }
                    return value;
                }
                
                // Initialize charts
                updateMetrics();
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def metrics_json(self, request):
        """Return metrics as JSON."""
        stats = self.monitor.get_statistics()
        return web.json_response(stats)
    
    async def metrics_prometheus(self, request):
        """Return metrics in Prometheus format."""
        stats = self.monitor.get_statistics()
        
        prometheus_metrics = []
        for metric_name, value in stats.items():
            if isinstance(value, dict):
                for sub_metric, sub_value in value.items():
                    if isinstance(sub_value, (int, float)):
                        prometheus_metrics.append(
                            f"i3_gateway_{metric_name}_{sub_metric} {sub_value}"
                        )
            elif isinstance(value, (int, float)):
                prometheus_metrics.append(f"i3_gateway_{metric_name} {value}")
        
        return web.Response(
            text='\n'.join(prometheus_metrics),
            content_type='text/plain'
        )
```

## Load Testing

### Comprehensive Load Test Suite

```python
# tests/load_test.py
import asyncio
import aiohttp
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import websockets
import json

class LoadTester:
    """Comprehensive load testing framework."""
    
    def __init__(self, gateway_url, api_key, max_connections=1000):
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.max_connections = max_connections
        self.results = {
            'connection_times': [],
            'message_latencies': [],
            'errors': [],
            'throughput': 0
        }
    
    async def run_connection_test(self, num_connections=100):
        """Test connection establishment performance."""
        print(f"Testing {num_connections} concurrent connections...")
        
        async def connect_and_measure():
            start_time = time.time()
            try:
                uri = self.gateway_url.replace('http', 'ws') + '/ws'
                async with websockets.connect(uri) as ws:
                    # Authenticate
                    auth_msg = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "authenticate",
                        "params": {"api_key": self.api_key}
                    }
                    await ws.send(json.dumps(auth_msg))
                    response = await ws.recv()
                    
                    connection_time = time.time() - start_time
                    self.results['connection_times'].append(connection_time)
                    
                    # Keep connection alive briefly
                    await asyncio.sleep(0.1)
            except Exception as e:
                self.results['errors'].append(str(e))
        
        # Create connections concurrently
        tasks = [connect_and_measure() for _ in range(num_connections)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        if self.results['connection_times']:
            avg_time = statistics.mean(self.results['connection_times'])
            p95_time = statistics.quantiles(self.results['connection_times'], n=20)[18]
            print(f"Average connection time: {avg_time:.3f}s")
            print(f"95th percentile: {p95_time:.3f}s")
            print(f"Errors: {len(self.results['errors'])}")
    
    async def run_throughput_test(self, duration=60, messages_per_second=100):
        """Test message throughput."""
        print(f"Testing throughput: {messages_per_second} msg/s for {duration}s")
        
        start_time = time.time()
        messages_sent = 0
        
        async def message_sender(ws):
            nonlocal messages_sent
            while time.time() - start_time < duration:
                message = {
                    "jsonrpc": "2.0",
                    "id": messages_sent,
                    "method": "ping"
                }
                
                message_start = time.time()
                await ws.send(json.dumps(message))
                response = await ws.recv()
                latency = time.time() - message_start
                
                self.results['message_latencies'].append(latency)
                messages_sent += 1
                
                # Rate limiting
                await asyncio.sleep(1.0 / messages_per_second)
        
        # Create multiple connections for load
        num_connections = min(10, self.max_connections)
        connections = []
        
        try:
            # Establish connections
            for i in range(num_connections):
                uri = self.gateway_url.replace('http', 'ws') + '/ws'
                ws = await websockets.connect(uri)
                
                # Authenticate
                auth_msg = {
                    "jsonrpc": "2.0",
                    "id": f"auth_{i}",
                    "method": "authenticate",
                    "params": {"api_key": self.api_key}
                }
                await ws.send(json.dumps(auth_msg))
                await ws.recv()  # Auth response
                
                connections.append(ws)
            
            # Start message senders
            tasks = [message_sender(ws) for ws in connections]
            await asyncio.gather(*tasks, return_exceptions=True)
            
        finally:
            # Close connections
            for ws in connections:
                await ws.close()
        
        # Calculate results
        total_time = time.time() - start_time
        self.results['throughput'] = messages_sent / total_time
        
        if self.results['message_latencies']:
            avg_latency = statistics.mean(self.results['message_latencies'])
            p95_latency = statistics.quantiles(self.results['message_latencies'], n=20)[18]
            print(f"Messages sent: {messages_sent}")
            print(f"Throughput: {self.results['throughput']:.1f} msg/s")
            print(f"Average latency: {avg_latency*1000:.1f}ms")
            print(f"95th percentile latency: {p95_latency*1000:.1f}ms")
    
    async def run_stress_test(self, target_failure_rate=0.05):
        """Stress test to find breaking point."""
        print("Running stress test to find breaking point...")
        
        connection_counts = [100, 200, 500, 1000, 2000, 5000]
        
        for count in connection_counts:
            if count > self.max_connections:
                break
            
            print(f"\nTesting {count} connections...")
            self.results = {'connection_times': [], 'errors': []}
            
            await self.run_connection_test(count)
            
            error_rate = len(self.results['errors']) / count
            print(f"Error rate: {error_rate:.2%}")
            
            if error_rate > target_failure_rate:
                print(f"Breaking point reached at {count} connections")
                break
            
            # Brief pause between tests
            await asyncio.sleep(5)

async def main():
    """Run comprehensive load tests."""
    tester = LoadTester("http://localhost:8080", "demo-key-123")
    
    print("=== I3 Gateway Load Testing ===\n")
    
    # Connection test
    await tester.run_connection_test(100)
    
    # Throughput test
    await tester.run_throughput_test(duration=30, messages_per_second=200)
    
    # Stress test
    await tester.run_stress_test()
    
    print("\n=== Load testing complete ===")

if __name__ == "__main__":
    asyncio.run(main())
```

## Scaling Strategies

### Horizontal Scaling

```yaml
# docker-compose.yml - Multi-instance deployment
version: '3.8'

services:
  gateway-1:
    build: .
    ports:
      - "8080:8080"
    environment:
      - INSTANCE_ID=1
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - nginx
    
  gateway-2:
    build: .
    ports:
      - "8081:8080"
    environment:
      - INSTANCE_ID=2
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - nginx
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - gateway-1
      - gateway-2
  
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

```nginx
# nginx.conf - Load balancer configuration
upstream gateway_backend {
    least_conn;
    server gateway-1:8080 max_fails=3 fail_timeout=30s;
    server gateway-2:8080 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    
    location /ws {
        proxy_pass http://gateway_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket timeouts
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
    
    location / {
        proxy_pass http://gateway_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Microservices Architecture

```python
# src/distributed/service_mesh.py
import asyncio
import aioredis
from typing import Dict, List

class ServiceMesh:
    """Distributed service mesh for scaling."""
    
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.services = {}
        self.instance_id = None
    
    async def initialize(self, instance_id):
        """Initialize service mesh."""
        self.instance_id = instance_id
        self.redis = await aioredis.from_url(self.redis_url)
        
        # Register this instance
        await self.register_instance()
        
        # Start service discovery
        asyncio.create_task(self.service_discovery_loop())
    
    async def register_instance(self):
        """Register this instance in the mesh."""
        instance_info = {
            'id': self.instance_id,
            'host': 'localhost',
            'port': 8080,
            'services': ['api', 'websocket', 'tcp'],
            'capacity': 1000,
            'current_load': 0
        }
        
        await self.redis.hset(
            'instances',
            self.instance_id,
            json.dumps(instance_info)
        )
        
        # Set TTL for health checking
        await self.redis.expire(f'instance:{self.instance_id}', 60)
    
    async def service_discovery_loop(self):
        """Continuous service discovery."""
        while True:
            try:
                # Get all instances
                instances = await self.redis.hgetall('instances')
                
                # Update local service registry
                for instance_id, info_json in instances.items():
                    info = json.loads(info_json)
                    self.services[instance_id] = info
                
                # Health check
                await self.health_check()
                
                await asyncio.sleep(10)
            except Exception as e:
                print(f"Service discovery error: {e}")
    
    async def route_request(self, request_type, payload):
        """Route request to appropriate instance."""
        # Find best instance for request type
        candidates = [
            info for info in self.services.values()
            if request_type in info.get('services', [])
        ]
        
        if not candidates:
            raise Exception(f"No instances available for {request_type}")
        
        # Load balancing - choose least loaded
        best_instance = min(candidates, key=lambda x: x['current_load'])
        
        # Forward request
        return await self.forward_request(best_instance, payload)
    
    async def forward_request(self, instance, payload):
        """Forward request to specific instance."""
        # Implement request forwarding logic
        # This would use HTTP client or direct API calls
        pass
```

## Troubleshooting Performance Issues

### Performance Debugging Tools

```python
# src/debugging/profiler.py
import cProfile
import pstats
import io
import time
import asyncio
from functools import wraps

class PerformanceProfiler:
    """Performance profiling and debugging tools."""
    
    def __init__(self):
        self.profiles = {}
        self.hotspots = []
    
    def profile_function(self, func):
        """Decorator to profile specific functions."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            pr = cProfile.Profile()
            pr.enable()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                pr.disable()
                
                # Store profile data
                s = io.StringIO()
                ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
                ps.print_stats()
                
                self.profiles[func.__name__] = s.getvalue()
        
        return wrapper
    
    async def profile_async_function(self, func):
        """Profile async functions."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                self.record_timing(func.__name__, duration)
        
        return wrapper
    
    def find_bottlenecks(self):
        """Analyze profiles to find bottlenecks."""
        bottlenecks = []
        
        for func_name, profile_data in self.profiles.items():
            lines = profile_data.split('\n')
            for line in lines:
                if 'cumulative' in line and 'seconds' in line:
                    # Parse timing information
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].replace('.', '').isdigit():
                        time_spent = float(parts[1])
                        if time_spent > 0.1:  # Functions taking >100ms
                            bottlenecks.append({
                                'function': func_name,
                                'time': time_spent,
                                'line': line.strip()
                            })
        
        return sorted(bottlenecks, key=lambda x: x['time'], reverse=True)

class MemoryProfiler:
    """Memory usage profiling."""
    
    def __init__(self):
        self.snapshots = []
    
    async def take_snapshot(self, label=""):
        """Take memory snapshot."""
        import tracemalloc
        import gc
        
        # Force garbage collection
        gc.collect()
        
        # Take snapshot
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        self.snapshots.append({
            'label': label,
            'timestamp': time.time(),
            'snapshot': snapshot,
            'top_stats': top_stats[:10]  # Top 10 memory consumers
        })
    
    def compare_snapshots(self, snapshot1_idx, snapshot2_idx):
        """Compare two memory snapshots."""
        if (snapshot1_idx >= len(self.snapshots) or 
            snapshot2_idx >= len(self.snapshots)):
            return None
        
        snap1 = self.snapshots[snapshot1_idx]['snapshot']
        snap2 = self.snapshots[snapshot2_idx]['snapshot']
        
        top_stats = snap2.compare_to(snap1, 'lineno')
        
        return {
            'total_diff': sum(stat.size_diff for stat in top_stats),
            'top_differences': top_stats[:10]
        }
```

### Performance Alert System

```python
# src/monitoring/alerts.py
import asyncio
import smtplib
from email.mime.text import MIMEText

class PerformanceAlertSystem:
    """Alert system for performance issues."""
    
    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {
            'api_latency_p99': 100,  # ms
            'memory_usage_mb': 500,
            'cpu_percent': 80,
            'error_rate': 0.05,
            'connection_failures': 10
        }
        
        self.alert_history = {}
        self.cooldown_period = 300  # 5 minutes between alerts
    
    async def check_performance(self, metrics):
        """Check metrics against thresholds."""
        alerts = []
        
        for metric, threshold in self.thresholds.items():
            if metric in metrics:
                value = metrics[metric]
                
                if self.should_alert(metric, value, threshold):
                    alert = {
                        'metric': metric,
                        'value': value,
                        'threshold': threshold,
                        'severity': self.get_severity(metric, value, threshold),
                        'timestamp': time.time()
                    }
                    alerts.append(alert)
                    
                    # Record alert
                    self.alert_history[metric] = alert['timestamp']
        
        if alerts:
            await self.send_alerts(alerts)
    
    def should_alert(self, metric, value, threshold):
        """Check if alert should be sent."""
        # Check if value exceeds threshold
        if value <= threshold:
            return False
        
        # Check cooldown period
        last_alert = self.alert_history.get(metric, 0)
        if time.time() - last_alert < self.cooldown_period:
            return False
        
        return True
    
    def get_severity(self, metric, value, threshold):
        """Determine alert severity."""
        ratio = value / threshold
        
        if ratio > 2:
            return 'critical'
        elif ratio > 1.5:
            return 'warning'
        else:
            return 'info'
    
    async def send_alerts(self, alerts):
        """Send alerts via email or webhook."""
        for alert in alerts:
            print(f"ALERT: {alert['metric']} = {alert['value']} "
                  f"(threshold: {alert['threshold']}) - {alert['severity']}")
            
            # Send email alert
            await self.send_email_alert(alert)
            
            # Send webhook alert
            await self.send_webhook_alert(alert)
    
    async def send_email_alert(self, alert):
        """Send email alert."""
        # Implement email sending logic
        pass
    
    async def send_webhook_alert(self, alert):
        """Send webhook alert."""
        # Implement webhook sending logic
        pass
```

This performance tuning guide provides comprehensive optimization strategies for the Intermud3 Gateway. Implement these optimizations incrementally and measure the impact of each change. Monitor the system continuously to ensure optimal performance under various load conditions.