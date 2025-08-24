"""MudMode protocol implementation for Intermud-3 communication.

This module handles the binary MudMode protocol used for communication
between MUDs and I3 routers.
"""

import asyncio
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from .lpc import LPCDecoder, LPCEncoder, LPCError


class MudModeError(Exception):
    """Base exception for MudMode protocol errors."""


@dataclass
class I3Packet:
    """Basic I3 packet structure.

    This is a temporary structure that will be replaced by proper
    packet models in src/models/packet.py
    """

    packet_type: str
    ttl: int
    originator_mud: str
    originator_user: str
    target_mud: str
    target_user: str
    payload: list[Any]

    def to_lpc_array(self) -> list[Any]:
        """Convert packet to LPC array format."""
        return [
            self.packet_type,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
            *self.payload,
        ]

    @classmethod
    def from_lpc_array(cls, data: list[Any]) -> "I3Packet":
        """Create packet from LPC array format."""
        if len(data) < 6:
            raise MudModeError(f"Invalid packet array: too few elements ({len(data)})")

        return cls(
            packet_type=str(data[0]) if data[0] else "",
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
            payload=data[6:] if len(data) > 6 else [],
        )


class MudModeProtocol:
    """Handles MudMode binary protocol communication.

    The MudMode protocol uses a simple framing format:
    - 4 bytes: message length (big-endian)
    - N bytes: LPC-encoded message data
    """

    def __init__(self):
        """Initialize the MudMode protocol handler."""
        self.lpc_encoder = LPCEncoder()
        self.lpc_decoder = LPCDecoder()
        self._receive_buffer = BytesIO()
        self._expected_length: int | None = None

    def encode_packet(self, packet: I3Packet) -> bytes:
        """Encode an I3 packet to MudMode binary format.

        Args:
            packet: I3 packet to encode

        Returns:
            Encoded bytes with length prefix

        Raises:
            MudModeError: If encoding fails
        """
        try:
            # Convert packet to LPC array format
            lpc_data = packet.to_lpc_array()

            # Encode to LPC binary format
            encoded = self.lpc_encoder.encode(lpc_data)

            # Add 4-byte length prefix
            length = struct.pack(">I", len(encoded))

            return length + encoded
        except (LPCError, Exception) as e:
            raise MudModeError(f"Failed to encode packet: {e}")

    def encode_raw(self, data: Any) -> bytes:
        """Encode raw data to MudMode binary format.

        Args:
            data: Raw data structure to encode

        Returns:
            Encoded bytes with length prefix

        Raises:
            MudModeError: If encoding fails
        """
        try:
            # Encode to LPC binary format
            encoded = self.lpc_encoder.encode(data)

            # Add 4-byte length prefix
            length = struct.pack(">I", len(encoded))

            return length + encoded
        except (LPCError, Exception) as e:
            raise MudModeError(f"Failed to encode data: {e}")

    def decode_packet(self, data: bytes) -> I3Packet | None:
        """Decode MudMode binary data to an I3 packet.

        Args:
            data: Binary data with length prefix

        Returns:
            Decoded I3 packet or None if insufficient data

        Raises:
            MudModeError: If decoding fails
        """
        result = self.decode_raw(data)
        if result is None:
            return None

        if not isinstance(result, list):
            raise MudModeError(f"Expected list for packet, got {type(result)}")

        return I3Packet.from_lpc_array(result)

    def decode_raw(self, data: bytes) -> Any | None:
        """Decode MudMode binary data to raw structure.

        Args:
            data: Binary data with length prefix

        Returns:
            Decoded data or None if insufficient data

        Raises:
            MudModeError: If decoding fails
        """
        if len(data) < 4:
            return None

        # Extract length prefix
        length = struct.unpack(">I", data[:4])[0]

        if len(data) < 4 + length:
            return None

        try:
            # Decode LPC data
            lpc_data = data[4 : 4 + length]
            result = self.lpc_decoder.decode(lpc_data)

            return result
        except (LPCError, Exception) as e:
            raise MudModeError(f"Failed to decode data: {e}")

    def feed_data(self, data: bytes) -> list[Any]:
        """Feed raw data to the protocol handler.

        This method handles partial data and buffering for stream-based
        protocols like TCP.

        Args:
            data: Raw bytes received from the network

        Returns:
            List of decoded messages (packets or raw data)
        """
        messages = []

        # Add new data to buffer
        self._receive_buffer.write(data)

        # Try to extract complete messages
        while True:
            # Reset to read position
            self._receive_buffer.seek(0)
            available = self._receive_buffer.tell()
            self._receive_buffer.seek(0)

            # Need at least 4 bytes for length
            if self._expected_length is None:
                length_bytes = self._receive_buffer.read(4)
                if len(length_bytes) < 4:
                    # Not enough data for length
                    self._receive_buffer.seek(0)
                    break

                self._expected_length = struct.unpack(">I", length_bytes)[0]

            # Check if we have the complete message
            self._receive_buffer.seek(4)  # Skip length bytes
            message_data = self._receive_buffer.read(self._expected_length)

            if len(message_data) < self._expected_length:
                # Not enough data for complete message
                self._receive_buffer.seek(0)
                break

            # Decode the message
            try:
                decoded = self.lpc_decoder.decode(message_data)
                messages.append(decoded)
            except LPCError as e:
                # Log error but continue processing
                # In production, this should use proper logging
                print(f"Error decoding message: {e}")

            # Remove processed data from buffer
            remaining = self._receive_buffer.read()
            self._receive_buffer = BytesIO()
            self._receive_buffer.write(remaining)
            self._expected_length = None

        return messages

    def reset(self):
        """Reset the protocol state.

        This should be called when the connection is reset or closed.
        """
        self._receive_buffer = BytesIO()
        self._expected_length = None


class MudModeStreamProtocol(asyncio.Protocol):
    """Asyncio protocol implementation for MudMode.

    This class integrates MudModeProtocol with asyncio's transport/protocol
    system for handling TCP connections.
    """

    def __init__(
        self,
        on_message: Callable[[Any], Awaitable[None]] | None = None,
        on_connection_lost: Callable[[], Awaitable[None]] | None = None,
    ):
        """Initialize the stream protocol.

        Args:
            on_message: Callback for received messages
            on_connection_lost: Callback for connection loss
        """
        self.mudmode = MudModeProtocol()
        self.transport: asyncio.Transport | None = None
        self.on_message = on_message
        self.on_connection_lost = on_connection_lost
        self._loop = asyncio.get_event_loop()

    def connection_made(self, transport: asyncio.Transport):
        """Called when connection is established."""
        self.transport = transport

    def data_received(self, data: bytes):
        """Called when data is received from the network."""
        messages = self.mudmode.feed_data(data)

        if self.on_message:
            for message in messages:
                # Schedule coroutine in event loop
                asyncio.create_task(self.on_message(message))

    def connection_lost(self, exc: Exception | None):
        """Called when connection is lost."""
        self.mudmode.reset()
        self.transport = None

        if self.on_connection_lost:
            asyncio.create_task(self.on_connection_lost())

    def send_message(self, data: Any) -> None:
        """Send a message through the connection.

        Args:
            data: Data to send (will be encoded as MudMode)

        Raises:
            MudModeError: If not connected or encoding fails
        """
        if not self.transport:
            raise MudModeError("Not connected")

        encoded = self.mudmode.encode_raw(data)
        self.transport.write(encoded)

    def send_packet(self, packet: I3Packet) -> None:
        """Send an I3 packet through the connection.

        Args:
            packet: I3 packet to send

        Raises:
            MudModeError: If not connected or encoding fails
        """
        if not self.transport:
            raise MudModeError("Not connected")

        encoded = self.mudmode.encode_packet(packet)
        self.transport.write(encoded)

    def close(self):
        """Close the connection."""
        if self.transport:
            self.transport.close()
