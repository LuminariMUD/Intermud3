"""Message queue system for offline clients and event buffering.

This module handles persistent message queuing for disconnected clients.
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueuedMessage:
    """A queued message with metadata."""
    
    session_id: str
    content: Any
    priority: int = 5  # 1-10, 1 is highest
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl: Optional[int] = None  # Time to live in seconds
    retry_count: int = 0
    max_retries: int = 3
    
    def is_expired(self) -> bool:
        """Check if message has expired.
        
        Returns:
            True if expired, False otherwise
        """
        if self.ttl is None:
            return False
        
        elapsed = (datetime.utcnow() - self.timestamp).total_seconds()
        return elapsed > self.ttl
    
    def __lt__(self, other: 'QueuedMessage') -> bool:
        """Compare messages by priority (lower number = higher priority)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp
    
    def __eq__(self, other: object) -> bool:
        """Check message equality."""
        if not isinstance(other, QueuedMessage):
            return False
        return (self.session_id == other.session_id and 
                self.content == other.content and
                self.priority == other.priority)
    
    def can_retry(self) -> bool:
        """Check if message can be retried.
        
        Returns:
            True if can retry, False otherwise
        """
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry count."""
        self.retry_count += 1


class PriorityMessageQueue:
    """Priority queue for messages."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize priority queue.
        
        Args:
            max_size: Maximum queue size
        """
        self.max_size = max_size
        self.queues: Dict[int, Deque[QueuedMessage]] = {
            i: deque() for i in range(1, 11)  # Priority 1-10
        }
        self.total_size = 0
    
    def put(self, message: QueuedMessage) -> bool:
        """Add message to queue.
        
        Args:
            message: Message to add
            
        Returns:
            True if added, False if queue full
        """
        if self.total_size >= self.max_size:
            # Try to remove expired messages first
            self._cleanup_expired()
            
            if self.total_size >= self.max_size:
                # Still full, drop lowest priority message
                if not self._drop_lowest_priority():
                    return False
        
        priority = max(1, min(10, message.priority))
        self.queues[priority].append(message)
        self.total_size += 1
        
        return True
    
    def get(self) -> Optional[QueuedMessage]:
        """Get highest priority message.
        
        Returns:
            Message if available, None otherwise
        """
        # Check queues in priority order
        for priority in range(1, 11):
            queue = self.queues[priority]
            
            # Skip expired messages
            while queue:
                message = queue[0]
                if message.is_expired():
                    queue.popleft()
                    self.total_size -= 1
                else:
                    # Found valid message
                    queue.popleft()
                    self.total_size -= 1
                    return message
        
        return None
    
    def peek(self) -> Optional[QueuedMessage]:
        """Peek at highest priority message without removing.
        
        Returns:
            Message if available, None otherwise
        """
        for priority in range(1, 11):
            queue = self.queues[priority]
            
            # Skip expired messages
            while queue:
                message = queue[0]
                if message.is_expired():
                    queue.popleft()
                    self.total_size -= 1
                else:
                    return message
        
        return None
    
    def size(self) -> int:
        """Get total queue size.
        
        Returns:
            Number of messages in queue
        """
        return self.total_size
    
    def is_empty(self) -> bool:
        """Check if queue is empty.
        
        Returns:
            True if empty, False otherwise
        """
        return self.total_size == 0
    
    def is_full(self) -> bool:
        """Check if queue is full.
        
        Returns:
            True if full, False otherwise
        """
        return self.total_size >= self.max_size
    
    def clear(self):
        """Clear all messages from queue."""
        for queue in self.queues.values():
            queue.clear()
        self.total_size = 0
    
    def _cleanup_expired(self):
        """Remove expired messages from all queues."""
        for priority in range(1, 11):
            queue = self.queues[priority]
            
            # Remove expired messages
            new_queue = deque()
            for message in queue:
                if not message.is_expired():
                    new_queue.append(message)
                else:
                    self.total_size -= 1
            
            self.queues[priority] = new_queue
    
    def _drop_lowest_priority(self) -> bool:
        """Drop lowest priority message to make room.
        
        Returns:
            True if message dropped, False if no messages to drop
        """
        # Start from lowest priority
        for priority in range(10, 0, -1):
            queue = self.queues[priority]
            if queue:
                queue.popleft()
                self.total_size -= 1
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_size": self.total_size,
            "max_size": self.max_size,
            "utilization": (self.total_size / self.max_size) * 100 if self.max_size > 0 else 0,
            "by_priority": {}
        }
        
        for priority in range(1, 11):
            size = len(self.queues[priority])
            if size > 0:
                stats["by_priority"][priority] = size
        
        return stats


class MessageQueueManager:
    """Manages message queues for all sessions."""
    
    def __init__(
        self,
        default_queue_size: int = 1000,
        default_ttl: int = 300,  # 5 minutes
        cleanup_interval: int = 60  # 1 minute
    ):
        """Initialize message queue manager.
        
        Args:
            default_queue_size: Default max queue size per session
            default_ttl: Default message TTL in seconds
            cleanup_interval: Cleanup interval in seconds
        """
        self.default_queue_size = default_queue_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        
        # Session queues
        self.session_queues: Dict[str, PriorityMessageQueue] = {}
        
        # Retry queues for failed messages
        self.retry_queues: Dict[str, List[QueuedMessage]] = {}
        
        # Worker task management
        self.running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.process_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            "messages_queued": 0,
            "messages_delivered": 0,
            "messages_expired": 0,
            "messages_dropped": 0,
            "retry_attempts": 0
        }
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the queue manager."""
        if self.running:
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._cleanup_loop())
        self.process_task = asyncio.create_task(self._process_loop())
        logger.info("Message queue manager started")
    
    async def stop(self):
        """Stop the queue manager."""
        self.running = False
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self.worker_task = None
            
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
            self.process_task = None
        
        logger.info("Message queue manager stopped")
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired messages."""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._cleanup_all_queues()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _process_loop(self):
        """Periodic processing of message queues."""
        while self.running:
            try:
                await self.process_queues()
                await asyncio.sleep(0.1)  # Process queues frequently
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
    
    def get_or_create_queue(self, session_id: str) -> PriorityMessageQueue:
        """Get or create a queue for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Priority message queue for the session
        """
        if session_id not in self.session_queues:
            self.session_queues[session_id] = PriorityMessageQueue(self.default_queue_size)
        return self.session_queues[session_id]
    
    def enqueue_message(
        self,
        session_id: str,
        content: Any,
        priority: int = 5,
        ttl: Optional[int] = None
    ) -> bool:
        """Enqueue a message for a session.
        
        Args:
            session_id: Session ID
            content: Message content
            priority: Message priority (1-10, 1 is highest)
            ttl: Time to live in seconds
            
        Returns:
            True if enqueued, False otherwise
        """
        queue = self.get_or_create_queue(session_id)
        message = QueuedMessage(
            session_id=session_id,
            content=content,
            priority=priority,
            ttl=ttl or self.default_ttl
        )
        
        success = queue.put(message)
        if success:
            self.stats["messages_queued"] += 1
        return success
    
    def _cleanup_all_queues(self):
        """Clean up expired messages from all queues."""
        expired_count = 0
        
        for session_id, queue in self.session_queues.items():
            initial_size = queue.size()
            queue._cleanup_expired()
            expired_count += initial_size - queue.size()
        
        if expired_count > 0:
            self.stats["messages_expired"] += expired_count
            logger.debug(f"Cleaned up {expired_count} expired messages")
    
    def queue_message(
        self,
        session_id: str,
        message: str,
        priority: int = 5,
        ttl: Optional[int] = None
    ) -> bool:
        """Queue message for session.
        
        Args:
            session_id: Session ID
            message: Message to queue
            priority: Message priority (1-10)
            ttl: Time to live in seconds
            
        Returns:
            True if queued, False if dropped
        """
        # Create queue if doesn't exist
        if session_id not in self.queues:
            self.queues[session_id] = PriorityQueue(self.default_queue_size)
        
        # Create queued message
        queued_msg = QueuedMessage(
            message=message,
            priority=priority,
            ttl=ttl or self.default_ttl
        )
        
        # Add to queue
        if self.queues[session_id].put(queued_msg):
            self.stats["messages_queued"] += 1
            return True
        else:
            self.stats["messages_dropped"] += 1
            logger.warning(f"Dropped message for session {session_id}: queue full")
            return False
    
    def get_message(self, session_id: str) -> Optional[str]:
        """Get next message for session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Message if available, None otherwise
        """
        if session_id not in self.queues:
            return None
        
        queued_msg = self.queues[session_id].get()
        if queued_msg:
            self.stats["messages_delivered"] += 1
            return queued_msg.message
        
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = dict(self.stats)
        stats["session_queues"] = {}
        
        for session_id, queue in self.session_queues.items():
            stats["session_queues"][session_id] = {
                "size": queue.size(),
                "max_size": queue.max_size
            }
        
        return stats
    
    def cleanup_empty_queues(self):
        """Remove empty session queues."""
        empty_sessions = [
            session_id for session_id, queue in self.session_queues.items()
            if queue.size() == 0
        ]
        
        for session_id in empty_sessions:
            del self.session_queues[session_id]
            logger.debug(f"Removed empty queue for session {session_id}")
    
    def remove_session_queue(self, session_id: str):
        """Remove a session's queue.
        
        Args:
            session_id: Session ID to remove
        """
        if session_id in self.session_queues:
            del self.session_queues[session_id]
            logger.info(f"Removed queue for session {session_id}")
    
    def clear_all_queues(self):
        """Clear all session queues."""
        for queue in self.session_queues.values():
            queue.clear()
        logger.info("Cleared all session queues")
    
    async def process_queues(self):
        """Process messages from all queues, delivering to sessions."""
        # Import here to avoid circular imports
        from src.api.session import session_manager
        
        # Make a copy of the keys to avoid dictionary changed size during iteration
        session_ids = list(self.session_queues.keys())
        disconnected_sessions = []
        
        for session_id in session_ids:
            if session_id not in self.session_queues:
                continue
                
            queue = self.session_queues[session_id]
            session = session_manager.get_session(session_id) if session_manager else None
            
            # Skip if session doesn't exist or isn't connected
            if not session or not session.is_connected():
                # Mark for cleanup later
                disconnected_sessions.append(session_id)
                continue
            
            while queue.size() > 0:
                queued_msg = queue.get()
                if queued_msg:
                    try:
                        # Convert message content to JSON if needed
                        content = queued_msg.content
                        if isinstance(content, dict):
                            content = json.dumps(content)
                        
                        # Send to session
                        await session.send(content)
                        self.stats["messages_delivered"] += 1
                    except Exception as e:
                        logger.error(f"Failed to deliver message to session {session_id}: {e}")
                        # Re-queue with retry if possible
                        if queued_msg.can_retry():
                            self.add_retry_message(session_id, queued_msg)
                        else:
                            self.stats["messages_dropped"] += 1
        
        # Clean up queues for disconnected sessions
        for session_id in disconnected_sessions:
            if session_id in self.session_queues:
                del self.session_queues[session_id]
    
    def get_all_messages(self, session_id: str, limit: int = 100) -> List[str]:
        """Get all queued messages for session.
        
        Args:
            session_id: Session ID
            limit: Maximum messages to return
            
        Returns:
            List of messages
        """
        if session_id not in self.queues:
            return []
        
        messages = []
        queue = self.queues[session_id]
        
        while len(messages) < limit and not queue.is_empty():
            msg = self.get_message(session_id)
            if msg:
                messages.append(msg)
            else:
                break
        
        return messages
    
    def peek_message(self, session_id: str) -> Optional[str]:
        """Peek at next message without removing.
        
        Args:
            session_id: Session ID
            
        Returns:
            Message if available, None otherwise
        """
        if session_id not in self.queues:
            return None
        
        queued_msg = self.queues[session_id].peek()
        if queued_msg:
            return queued_msg.message
        
        return None
    
    def get_queue_size(self, session_id: str) -> int:
        """Get queue size for session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Number of queued messages
        """
        if session_id not in self.queues:
            return 0
        
        return self.queues[session_id].size()
    
    def clear_queue(self, session_id: str):
        """Clear all messages for session.
        
        Args:
            session_id: Session ID
        """
        if session_id in self.queues:
            self.queues[session_id].clear()
            logger.debug(f"Cleared queue for session {session_id}")
    
    def remove_session(self, session_id: str):
        """Remove session and its queue.
        
        Args:
            session_id: Session ID
        """
        if session_id in self.queues:
            del self.queues[session_id]
        
        if session_id in self.retry_queues:
            del self.retry_queues[session_id]
        
        logger.debug(f"Removed queue for session {session_id}")
    
    def add_retry_message(self, session_id: str, message: QueuedMessage):
        """Add message to retry queue.
        
        Args:
            session_id: Session ID
            message: Message to retry
        """
        if session_id not in self.retry_queues:
            self.retry_queues[session_id] = []
        
        message.increment_retry()
        self.retry_queues[session_id].append(message)
        self.stats["retry_attempts"] += 1
    
    async def process_retries(self, session_id: str) -> int:
        """Process retry messages for session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Number of messages retried
        """
        if session_id not in self.retry_queues:
            return 0
        
        messages = self.retry_queues[session_id]
        self.retry_queues[session_id] = []
        
        retried = 0
        for msg in messages:
            if msg.can_retry() and not msg.is_expired():
                # Re-queue the message
                if self.queue_message(
                    session_id,
                    msg.message,
                    msg.priority,
                    msg.ttl
                ):
                    retried += 1
            else:
                self.stats["messages_dropped"] += 1
        
        return retried
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue manager statistics.
        
        Returns:
            Statistics dictionary
        """
        total_queued = sum(q.size() for q in self.queues.values())
        total_retry = sum(len(q) for q in self.retry_queues.values())
        
        return {
            **self.stats,
            "active_queues": len(self.queues),
            "total_queued": total_queued,
            "total_retry": total_retry,
            "queue_details": {
                session_id: queue.get_stats()
                for session_id, queue in self.queues.items()
            }
        }


# Global message queue manager instance
message_queue_manager = MessageQueueManager()