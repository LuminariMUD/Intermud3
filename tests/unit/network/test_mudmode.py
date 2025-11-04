"""Unit tests for MudMode protocol implementation."""

import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.network.lpc import LPCError
from src.network.mudmode import I3Packet, MudModeError, MudModeProtocol


class TestMudModeError:
    """Test MudModeError exception."""

    def test_mudmode_error_creation(self):
        """Test MudModeError creation."""
        error = MudModeError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)


class TestI3Packet:
    """Test I3Packet dataclass functionality."""

    def test_packet_creation(self):
        """Test I3Packet creation with all fields."""
        packet = I3Packet(
            packet_type="tell",
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            payload=["message", "content"],
        )

        assert packet.packet_type == "tell"
        assert packet.ttl == 200
        assert packet.originator_mud == "TestMUD"
        assert packet.originator_user == "testuser"
        assert packet.target_mud == "TargetMUD"
        assert packet.target_user == "targetuser"
        assert packet.payload == ["message", "content"]

    def test_packet_to_lpc_array(self):
        """Test conversion to LPC array format."""
        packet = I3Packet(
            packet_type="tell",
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            payload=["Hello", "World"],
        )

        lpc_array = packet.to_lpc_array()

        expected = ["tell", 200, "TestMUD", "testuser", "TargetMUD", "targetuser", "Hello", "World"]
        assert lpc_array == expected

    def test_packet_from_lpc_array_success(self):
        """Test creation from LPC array."""
        lpc_array = [
            "tell",
            200,
            "TestMUD",
            "testuser",
            "TargetMUD",
            "targetuser",
            "Hello",
            "World",
        ]

        packet = I3Packet.from_lpc_array(lpc_array)

        assert packet.packet_type == "tell"
        assert packet.ttl == 200
        assert packet.originator_mud == "TestMUD"
        assert packet.originator_user == "testuser"
        assert packet.target_mud == "TargetMUD"
        assert packet.target_user == "targetuser"
        assert packet.payload == ["Hello", "World"]

    def test_packet_from_lpc_array_too_few_elements(self):
        """Test creation from array with too few elements."""
        lpc_array = ["tell", 200, "TestMUD"]  # Missing required fields

        with pytest.raises(MudModeError, match="too few elements"):
            I3Packet.from_lpc_array(lpc_array)


class TestMudModeProtocol:
    """Test MudModeProtocol functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.protocol = MudModeProtocol()
        self.test_packet = I3Packet(
            packet_type="tell",
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            payload=["Hello", "World"],
        )

    def test_protocol_initialization(self):
        """Test protocol initialization."""
        protocol = MudModeProtocol()

        assert protocol.lpc_encoder is not None
        assert protocol.lpc_decoder is not None
        assert isinstance(protocol._receive_buffer, BytesIO)
        assert protocol._expected_length is None

    @patch("src.network.mudmode.LPCEncoder")
    def test_encode_packet_success(self, mock_encoder_class):
        """Test successful packet encoding."""
        mock_encoder = mock_encoder_class.return_value
        mock_encoder.encode.return_value = b"encoded_lpc_data"

        protocol = MudModeProtocol()
        result = protocol.encode_packet(self.test_packet)

        # Should have 4-byte length prefix
        assert len(result) > 4
        # Verify encoder was called with packet LPC array
        mock_encoder.encode.assert_called_once()
        call_args = mock_encoder.encode.call_args[0][0]
        assert call_args == self.test_packet.to_lpc_array()

    @patch("src.network.mudmode.LPCEncoder")
    def test_encode_packet_lpc_error(self, mock_encoder_class):
        """Test packet encoding with LPC error."""
        mock_encoder = mock_encoder_class.return_value
        mock_encoder.encode.side_effect = LPCError("Encoding failed")

        protocol = MudModeProtocol()

        with pytest.raises(MudModeError, match="Failed to encode packet"):
            protocol.encode_packet(self.test_packet)

    def test_reset(self):
        """Test protocol reset."""
        protocol = MudModeProtocol()

        # Set some state
        protocol._receive_buffer.write(b"test_data")
        protocol._expected_length = 100

        protocol.reset()

        # Should be reset to initial state
        assert isinstance(protocol._receive_buffer, BytesIO)
        assert protocol._expected_length is None
