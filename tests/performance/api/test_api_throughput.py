"""API throughput performance tests."""

import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.server import APIServer
from src.api.session import SessionManager
from src.api.events import EventDispatcher
from src.config.models import APIConfig


@pytest.fixture
def api_config():
    """Create API configuration for performance testing."""
    return APIConfig(
        host="127.0.0.1",
        port=8080
    )


@pytest.fixture
def mock_gateway():
    """Create mock gateway for performance testing."""
    gateway = MagicMock()
    gateway.is_connected.return_value = True
    gateway.send_packet = AsyncMock()
    return gateway


@pytest.fixture
async def api_server(api_config, mock_gateway):
    """Create API server for performance testing."""
    server = APIServer(api_config, mock_gateway)
    
    # Mock event system components
    with patch('src.api.server.event_dispatcher'), \
         patch('src.api.server.message_queue_manager'), \
         patch('src.api.server.event_bridge'):
        
        await server.start()
        yield server
        await server.stop()


@pytest.fixture
async def authenticated_session(api_server):
    """Create authenticated session for testing."""
    # Mock authentication
    with patch.object(api_server.session_manager.auth, 'authenticate') as mock_auth:
        mock_auth.return_value = {
            'mud_name': 'TestMUD',
            'permissions': {'tell', 'channel', 'who', 'finger'}
        }
        
        session = await api_server.session_manager.authenticate("test-credential")
        yield session


class TestMessageThroughput:
    """Test message processing throughput."""
    
    @pytest.mark.asyncio
    async def test_tell_message_throughput(self, api_server, authenticated_session):
        """Test tell message processing throughput."""
        message_count = 1000
        messages = []
        
        # Prepare tell messages
        for i in range(message_count):
            message = {
                "jsonrpc": "2.0",
                "method": "tell",
                "params": {
                    "target_mud": "OtherMUD",
                    "target_user": f"user{i}",
                    "message": f"Test message {i}"
                },
                "id": str(i)
            }
            messages.append(json.dumps(message))
        
        # Mock session to avoid actual sending
        authenticated_session.send = AsyncMock()
        
        # Measure processing time
        start_time = time.time()
        
        # Process all messages
        tasks = []
        for message in messages:
            task = api_server.process_message(authenticated_session, message)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate throughput
        throughput = message_count / duration
        
        print(f"Processed {message_count} tell messages in {duration:.2f}s")
        print(f"Throughput: {throughput:.2f} messages/second")
        
        # Assert minimum throughput (should be much higher in practice)
        assert throughput > 100, f"Throughput too low: {throughput:.2f} msg/s"
        
        # Verify all messages were processed
        assert authenticated_session.send.call_count == message_count
    
    @pytest.mark.asyncio
    async def test_mixed_message_throughput(self, api_server, authenticated_session):
        """Test mixed message type processing throughput."""
        message_count = 500
        messages = []
        
        # Prepare mixed messages
        for i in range(message_count):
            if i % 3 == 0:
                # Tell message
                message = {
                    "jsonrpc": "2.0",
                    "method": "tell",
                    "params": {
                        "target_mud": "OtherMUD",
                        "target_user": f"user{i}",
                        "message": f"Tell message {i}"
                    },
                    "id": str(i)
                }
            elif i % 3 == 1:
                # Channel message
                message = {
                    "jsonrpc": "2.0",
                    "method": "channel_message",
                    "params": {
                        "channel": "chat",
                        "message": f"Channel message {i}"
                    },
                    "id": str(i)
                }
            else:
                # Who request
                message = {
                    "jsonrpc": "2.0",
                    "method": "who_request",
                    "params": {
                        "target_mud": "OtherMUD"
                    },
                    "id": str(i)
                }
            
            messages.append(json.dumps(message))
        
        # Mock session
        authenticated_session.send = AsyncMock()
        
        # Measure processing time
        start_time = time.time()
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = api_server.process_message(authenticated_session, message)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate throughput
        throughput = message_count / duration
        
        print(f"Processed {message_count} mixed messages in {duration:.2f}s")
        print(f"Throughput: {throughput:.2f} messages/second")
        
        # Assert minimum throughput
        assert throughput > 50, f"Mixed message throughput too low: {throughput:.2f} msg/s"
    
    @pytest.mark.asyncio
    async def test_concurrent_sessions_throughput(self, api_server):
        """Test throughput with multiple concurrent sessions."""
        session_count = 10
        messages_per_session = 100
        
        # Create multiple sessions
        sessions = []
        with patch.object(api_server.session_manager.auth, 'authenticate') as mock_auth:
            mock_auth.return_value = {
                'mud_name': 'TestMUD',
                'permissions': {'tell', 'channel'}
            }
            
            for i in range(session_count):
                session = await api_server.session_manager.authenticate(f"test-credential-{i}")
                session.send = AsyncMock()
                sessions.append(session)
        
        # Prepare messages for each session
        all_tasks = []
        
        start_time = time.time()
        
        for session_idx, session in enumerate(sessions):
            for msg_idx in range(messages_per_session):
                message = {
                    "jsonrpc": "2.0",
                    "method": "tell",
                    "params": {
                        "target_mud": "OtherMUD",
                        "target_user": f"user{msg_idx}",
                        "message": f"Message from session {session_idx}"
                    },
                    "id": f"{session_idx}-{msg_idx}"
                }
                
                task = api_server.process_message(session, json.dumps(message))
                all_tasks.append(task)
        
        # Process all messages concurrently
        await asyncio.gather(*all_tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        total_messages = session_count * messages_per_session
        throughput = total_messages / duration
        
        print(f"Processed {total_messages} messages from {session_count} sessions in {duration:.2f}s")
        print(f"Throughput: {throughput:.2f} messages/second")
        
        # Assert minimum throughput with concurrency
        assert throughput > 200, f"Concurrent throughput too low: {throughput:.2f} msg/s"
        
        # Verify all sessions processed their messages
        for session in sessions:
            assert session.send.call_count == messages_per_session


class TestEventThroughput:
    """Test event system throughput."""
    
    @pytest.mark.asyncio
    async def test_event_dispatch_throughput(self):
        """Test event dispatch throughput."""
        from src.api.events import EventDispatcher, EventType
        
        dispatcher = EventDispatcher()
        await dispatcher.start()
        
        try:
            # Mock sessions
            session_count = 5
            sessions = []
            
            for i in range(session_count):
                session = MagicMock()
                session.session_id = f"session-{i}"
                session.mud_name = "TestMUD"
                session.is_connected.return_value = True
                session.permissions = {"tell", "channel"}
                session.subscriptions = {"chat"}
                session.send = AsyncMock()
                
                dispatcher.register_session(session)
                sessions.append(session)
            
            # Create events
            event_count = 1000
            
            start_time = time.time()
            
            # Dispatch events
            tasks = []
            for i in range(event_count):
                event = dispatcher.create_event(
                    EventType.CHANNEL_MESSAGE,
                    {
                        "channel": "chat",
                        "from_mud": "OtherMUD",
                        "from_user": f"user{i}",
                        "message": f"Event message {i}"
                    },
                    priority=5
                )
                task = dispatcher.dispatch(event)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # Allow time for processing
            await asyncio.sleep(0.5)
            
            end_time = time.time()
            duration = end_time - start_time
            
            throughput = event_count / duration
            
            print(f"Dispatched {event_count} events to {session_count} sessions in {duration:.2f}s")
            print(f"Event throughput: {throughput:.2f} events/second")
            
            # Assert minimum event throughput
            assert throughput > 500, f"Event throughput too low: {throughput:.2f} events/s"
            
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_event_filtering_throughput(self):
        """Test event filtering performance with many sessions."""
        from src.api.events import EventDispatcher, EventType, EventFilter
        
        dispatcher = EventDispatcher()
        await dispatcher.start()
        
        try:
            # Create many sessions with different filters
            session_count = 20
            sessions = []
            
            for i in range(session_count):
                session = MagicMock()
                session.session_id = f"session-{i}"
                session.mud_name = f"MUD{i % 5}"  # 5 different MUDs
                session.is_connected.return_value = True
                session.permissions = {"tell", "channel"}
                session.subscriptions = {f"channel{i % 3}"}  # 3 different channels
                session.send = AsyncMock()
                
                # Set custom filter for some sessions
                if i % 2 == 0:
                    custom_filter = EventFilter(
                        event_types={EventType.CHANNEL_MESSAGE},
                        channels={f"channel{i % 3}"},
                        exclude_self=True
                    )
                    dispatcher.set_filter(session.session_id, custom_filter)
                
                dispatcher.register_session(session)
                sessions.append(session)
            
            # Generate events for different channels
            event_count = 500
            
            start_time = time.time()
            
            tasks = []
            for i in range(event_count):
                channel = f"channel{i % 3}"
                event = dispatcher.create_event(
                    EventType.CHANNEL_MESSAGE,
                    {
                        "channel": channel,
                        "from_mud": "ExternalMUD",
                        "from_user": f"user{i}",
                        "message": f"Filtered message {i}"
                    },
                    priority=5
                )
                task = dispatcher.dispatch(event)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # Allow time for processing
            await asyncio.sleep(0.5)
            
            end_time = time.time()
            duration = end_time - start_time
            
            throughput = event_count / duration
            
            print(f"Processed {event_count} filtered events for {session_count} sessions in {duration:.2f}s")
            print(f"Filtered event throughput: {throughput:.2f} events/second")
            
            # Assert reasonable performance with filtering
            assert throughput > 200, f"Filtered event throughput too low: {throughput:.2f} events/s"
            
        finally:
            await dispatcher.stop()


class TestSessionThroughput:
    """Test session management throughput."""
    
    @pytest.mark.asyncio
    async def test_session_creation_throughput(self):
        """Test session creation and cleanup throughput."""
        from src.api.session import SessionManager
        from src.config.models import APIConfig
        
        config = APIConfig(host="127.0.0.1", port=8080)
        manager = SessionManager(config)
        
        # Mock authentication
        with patch.object(manager.auth, 'authenticate') as mock_auth:
            mock_auth.return_value = {
                'mud_name': 'TestMUD',
                'permissions': {'tell', 'channel'}
            }
            
            session_count = 100
            
            # Test session creation
            start_time = time.time()
            
            sessions = []
            for i in range(session_count):
                session = await manager.authenticate(f"test-credential-{i}")
                sessions.append(session)
            
            creation_time = time.time() - start_time
            creation_throughput = session_count / creation_time
            
            print(f"Created {session_count} sessions in {creation_time:.2f}s")
            print(f"Session creation throughput: {creation_throughput:.2f} sessions/second")
            
            # Test session cleanup
            start_time = time.time()
            
            cleanup_tasks = []
            for session in sessions:
                task = manager.disconnect(session)
                cleanup_tasks.append(task)
            
            await asyncio.gather(*cleanup_tasks)
            
            cleanup_time = time.time() - start_time
            cleanup_throughput = session_count / cleanup_time
            
            print(f"Cleaned up {session_count} sessions in {cleanup_time:.2f}s")
            print(f"Session cleanup throughput: {cleanup_throughput:.2f} sessions/second")
            
            # Assert reasonable performance
            assert creation_throughput > 50, f"Session creation too slow: {creation_throughput:.2f} sessions/s"
            assert cleanup_throughput > 100, f"Session cleanup too slow: {cleanup_throughput:.2f} sessions/s"
            
            # Verify all sessions were cleaned up
            assert len(manager.sessions) == 0


class TestMemoryEfficiency:
    """Test memory efficiency under load."""
    
    @pytest.mark.asyncio
    async def test_message_queue_memory_efficiency(self, api_server, authenticated_session):
        """Test memory usage with large message queues."""
        import gc
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Queue many messages
        message_count = 5000
        
        for i in range(message_count):
            message = f"Large message {i} with lots of content " * 10
            authenticated_session.queue_message(message)
        
        # Check memory after queuing
        mid_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Flush all messages
        authenticated_session.send = AsyncMock()
        await authenticated_session.flush_queue()
        
        # Force garbage collection
        gc.collect()
        
        # Check final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Memory usage - Initial: {initial_memory:.1f}MB, Peak: {mid_memory:.1f}MB, Final: {final_memory:.1f}MB")
        
        # Memory should return close to initial after cleanup
        memory_increase = final_memory - initial_memory
        assert memory_increase < 50, f"Memory leak detected: {memory_increase:.1f}MB increase"
        
        # Verify queue was emptied
        assert len(authenticated_session.message_queue) == 0
    
    @pytest.mark.asyncio
    async def test_session_scaling_memory(self):
        """Test memory usage with many sessions."""
        import gc
        import psutil
        import os
        
        from src.api.session import SessionManager
        from src.config.models import APIConfig
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        config = APIConfig(host="127.0.0.1", port=8080)
        manager = SessionManager(config)
        
        # Mock authentication
        with patch.object(manager.auth, 'authenticate') as mock_auth:
            mock_auth.return_value = {
                'mud_name': 'TestMUD',
                'permissions': {'tell', 'channel'}
            }
            
            # Create many sessions
            session_count = 500
            sessions = []
            
            for i in range(session_count):
                session = await manager.authenticate(f"test-credential-{i}")
                sessions.append(session)
            
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Clean up sessions
            await manager.cleanup()
            gc.collect()
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"Session scaling - Initial: {initial_memory:.1f}MB, Peak: {peak_memory:.1f}MB, Final: {final_memory:.1f}MB")
            
            # Calculate memory per session
            memory_per_session = (peak_memory - initial_memory) / session_count
            print(f"Memory per session: {memory_per_session:.3f}MB")
            
            # Assert reasonable memory usage per session
            assert memory_per_session < 1.0, f"Too much memory per session: {memory_per_session:.3f}MB"
            
            # Verify cleanup
            memory_increase = final_memory - initial_memory
            assert memory_increase < 20, f"Memory not properly cleaned up: {memory_increase:.1f}MB remaining"