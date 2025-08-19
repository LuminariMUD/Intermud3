#!/usr/bin/env python3
"""
Comprehensive network integration test for I3 Gateway.
Tests connection, reconnection, failover, and packet handling.
"""

import asyncio
import struct
import time
from typing import List, Optional, Any
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.network.lpc import LPCEncoder
from src.network.mudmode import MudModeProtocol
from src.network.connection import ConnectionManager, ConnectionState
from src.models.packet import PacketFactory, StartupPacket, TellPacket
from src.config.models import RouterConfig, RouterHostConfig


class MockI3Router:
    """Mock I3 router for testing."""
    
    def __init__(self, port: int = 9999):
        self.port = port
        self.server = None
        self.clients = []
        self.received_packets = []
        self.encoder = LPCEncoder()
        self.should_reject = False
        self.disconnect_after = None
        
    async def start(self):
        """Start the mock router."""
        self.server = await asyncio.start_server(
            self.handle_client, '127.0.0.1', self.port
        )
        print(f"Mock router started on port {self.port}")
        
    async def stop(self):
        """Stop the mock router."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
    async def handle_client(self, reader, writer):
        """Handle a client connection."""
        addr = writer.get_extra_info('peername')
        print(f"Client connected from {addr}")
        self.clients.append((reader, writer))
        
        if self.should_reject:
            writer.close()
            await writer.wait_closed()
            return
            
        try:
            packet_count = 0
            while True:
                # Read packet length
                length_bytes = await reader.read(4)
                if not length_bytes:
                    break
                    
                length = struct.unpack('>I', length_bytes)[0]
                data = await reader.read(length)
                
                if not data:
                    break
                    
                # Decode packet
                packet_data = self.encoder.decode(data)
                self.received_packets.append(packet_data)
                print(f"Received packet: {packet_data[0] if packet_data else 'unknown'}")
                
                # Send response based on packet type
                if packet_data and packet_data[0] == 'startup-req-3':
                    await self.send_startup_reply(writer)
                elif packet_data and packet_data[0] == 'mudlist':
                    await self.send_mudlist_reply(writer)
                    
                packet_count += 1
                if self.disconnect_after and packet_count >= self.disconnect_after:
                    print(f"Disconnecting after {packet_count} packets")
                    break
                    
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            
    async def send_startup_reply(self, writer):
        """Send startup-reply packet."""
        reply = [
            'startup-reply',
            200,  # TTL
            '*i3',  # Router name
            0,  # O-user
            'TestMUD',  # Target mud
            0,  # T-user
            ['*i3', 1234],  # Router list
            10  # Password
        ]
        
        encoded = self.encoder.encode(reply)
        length = struct.pack('>I', len(encoded))
        writer.write(length + encoded)
        await writer.drain()
        print("Sent startup-reply")
        
    async def send_mudlist_reply(self, writer):
        """Send mudlist packet."""
        mudlist = [
            'mudlist',
            200,
            '*i3',
            0,
            'TestMUD',
            0,
            123456,  # ID
            {
                'TestMUD': {
                    'ip': '127.0.0.1',
                    'port': 4000,
                    'mudlib': 'Custom',
                    'status': 'open'
                },
                'OtherMUD': {
                    'ip': '192.168.1.1',
                    'port': 5000,
                    'mudlib': 'LP',
                    'status': 'open'
                }
            }
        ]
        
        encoded = self.encoder.encode(mudlist)
        length = struct.pack('>I', len(encoded))
        writer.write(length + encoded)
        await writer.drain()
        print("Sent mudlist")


async def test_basic_connection():
    """Test basic connection establishment."""
    print("\n=== Testing Basic Connection ===")
    
    # Start mock router
    router = MockI3Router(9999)
    await router.start()
    
    try:
        # Create connection manager
        config = RouterConfig(
            primary=RouterHostConfig(
                host="127.0.0.1",
                port=9999
            ),
            fallback=[]
        )
        
        manager = ConnectionManager(config)
        
        # Connect
        await manager.connect()
        assert manager.state == ConnectionState.CONNECTED
        print("✓ Connection established")
        
        # Send a test packet
        test_packet = ['test', 200, 'TestMUD', 'user', '*i3', 0, 'Hello']
        await manager.send_packet(test_packet)
        await asyncio.sleep(0.1)
        
        # Check router received it
        assert len(router.received_packets) > 0
        print(f"✓ Packet sent and received: {router.received_packets}")
        
        # Disconnect
        await manager.disconnect()
        assert manager.state == ConnectionState.DISCONNECTED
        print("✓ Disconnected cleanly")
        
    finally:
        await router.stop()
        

async def test_reconnection():
    """Test automatic reconnection."""
    print("\n=== Testing Automatic Reconnection ===")
    
    # Start mock router
    router = MockI3Router(9999)
    router.disconnect_after = 1  # Disconnect after first packet
    await router.start()
    
    try:
        config = RouterConfig(
            primary=RouterHostConfig(
                host="127.0.0.1",
                port=9999
            ),
            fallback=[]
        )
        
        manager = ConnectionManager(config)
        manager.reconnect_delay = 0.5  # Fast reconnect for testing
        
        # Connect
        await manager.connect()
        print("✓ Initial connection established")
        
        # Send packet (will trigger disconnect)
        await manager.send_packet(['test', 200, 'TestMUD', 'user', '*i3', 0, 'test'])
        
        # Wait for disconnect and reconnect
        await asyncio.sleep(1.0)
        
        # Should be reconnected
        assert manager.state == ConnectionState.CONNECTED
        print("✓ Reconnected after disconnect")
        
        await manager.disconnect()
        
    finally:
        await router.stop()


async def test_failover():
    """Test router failover."""
    print("\n=== Testing Router Failover ===")
    
    # Start backup router
    backup_router = MockI3Router(9998)
    await backup_router.start()
    
    try:
        config = RouterConfig(
            primary=RouterHostConfig(
                host="127.0.0.1",
                port=9999  # Primary not running
            ),
            fallback=[
                RouterHostConfig(
                    host="127.0.0.1",
                    port=9998
                )
            ]
        )
        
        manager = ConnectionManager(config)
        manager.reconnect_delay = 0.5
        
        # Try to connect (primary will fail)
        await manager.connect()
        
        # Should connect to backup
        assert manager.state == ConnectionState.CONNECTED
        assert manager.current_router['port'] == 9998
        print("✓ Failed over to backup router")
        
        # Test sending through backup
        await manager.send_packet(['test', 200, 'TestMUD', 'user', '*i3', 0, 'failover'])
        await asyncio.sleep(0.1)
        
        assert len(backup_router.received_packets) > 0
        print("✓ Packet sent through backup router")
        
        await manager.disconnect()
        
    finally:
        await backup_router.stop()


async def test_packet_encoding():
    """Test packet encoding and decoding."""
    print("\n=== Testing Packet Encoding/Decoding ===")
    
    protocol = MudModeProtocol()
    
    # Test various packet types
    packets = [
        ['tell', 200, 'MudA', 'userA', 'MudB', 'userB', 'userA', 'Hello!'],
        ['channel-m', 200, 'MudA', 'userA', 0, 0, 'chat', 'userA', 'Hello channel!'],
        ['who-req', 200, 'MudA', 'userA', 'MudB', 0],
        ['finger-req', 200, 'MudA', 'userA', 'MudB', 0, 'targetUser'],
    ]
    
    for packet in packets:
        # Encode
        encoded = protocol.encode_packet(packet)
        assert isinstance(encoded, bytes)
        assert len(encoded) > 4  # Has length prefix
        
        # Decode
        decoded = protocol.decode_packet(encoded)
        assert decoded == packet
        print(f"✓ Packet roundtrip successful: {packet[0]}")


async def test_connection_state_machine():
    """Test connection state transitions."""
    print("\n=== Testing Connection State Machine ===")
    
    router = MockI3Router(9999)
    await router.start()
    
    try:
        config = RouterConfig(
            primary="*i3",
            address="127.0.0.1",
            port=9999,
            fallback=[]
        )
        
        manager = ConnectionManager(config)
        
        # Initial state
        assert manager.state == ConnectionState.DISCONNECTED
        print("✓ Initial state: DISCONNECTED")
        
        # Connect
        await manager.connect()
        assert manager.state == ConnectionState.CONNECTED
        print("✓ After connect: CONNECTED")
        
        # Force error state
        if manager.writer:
            manager.writer.close()
            await manager.writer.wait_closed()
        manager.state = ConnectionState.ERROR
        print("✓ Forced to ERROR state")
        
        # Should auto-reconnect
        await asyncio.sleep(1.0)
        assert manager.state == ConnectionState.CONNECTED
        print("✓ Auto-recovered from ERROR to CONNECTED")
        
        await manager.disconnect()
        
    finally:
        await router.stop()


async def test_packet_buffering():
    """Test packet buffering during disconnection."""
    print("\n=== Testing Packet Buffering ===")
    
    router = MockI3Router(9999)
    
    try:
        config = RouterConfig(
            primary="*i3", 
            address="127.0.0.1",
            port=9999,
            fallback=[]
        )
        
        manager = ConnectionManager(config)
        manager.reconnect_delay = 0.5
        
        # Send packets while disconnected
        packets_to_send = [
            ['test1', 200, 'TestMUD', 'user', '*i3', 0, 'msg1'],
            ['test2', 200, 'TestMUD', 'user', '*i3', 0, 'msg2'],
            ['test3', 200, 'TestMUD', 'user', '*i3', 0, 'msg3'],
        ]
        
        for packet in packets_to_send:
            await manager.send_packet(packet)
        
        print(f"✓ Buffered {len(manager.outbound_queue)} packets while disconnected")
        
        # Now start router and connect
        await router.start()
        await manager.connect()
        
        # Wait for buffered packets to be sent
        await asyncio.sleep(0.5)
        
        # Check all packets were received
        assert len(router.received_packets) >= len(packets_to_send)
        print(f"✓ All buffered packets sent after connection")
        
        await manager.disconnect()
        
    finally:
        await router.stop()


async def test_performance():
    """Test performance metrics."""
    print("\n=== Testing Performance ===")
    
    router = MockI3Router(9999)
    await router.start()
    
    try:
        config = RouterConfig(
            primary="*i3",
            address="127.0.0.1",
            port=9999,
            fallback=[]
        )
        
        manager = ConnectionManager(config)
        await manager.connect()
        
        # Send many packets rapidly
        num_packets = 100
        start_time = time.time()
        
        for i in range(num_packets):
            packet = ['test', 200, 'TestMUD', 'user', '*i3', 0, f'msg{i}']
            await manager.send_packet(packet)
            
        # Wait for processing
        await asyncio.sleep(0.5)
        
        elapsed = time.time() - start_time
        rate = num_packets / elapsed
        
        print(f"✓ Sent {num_packets} packets in {elapsed:.2f}s")
        print(f"✓ Rate: {rate:.0f} packets/second")
        
        # Check latency
        assert rate > 100  # Should handle >100 packets/sec
        print("✓ Performance target met (>100 packets/sec)")
        
        await manager.disconnect()
        
    finally:
        await router.stop()


async def main():
    """Run all tests."""
    print("=" * 50)
    print("I3 GATEWAY NETWORK INTEGRATION TESTS")
    print("=" * 50)
    
    tests = [
        test_basic_connection,
        test_reconnection,
        test_failover, 
        test_packet_encoding,
        test_connection_state_machine,
        test_packet_buffering,
        test_performance,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)