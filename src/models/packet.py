"""I3 packet models and validation.

This module defines the packet structures used in the Intermud-3 protocol.
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional, Union, Type
from enum import Enum
from abc import ABC, abstractmethod


class PacketValidationError(Exception):
    """Raised when packet validation fails."""
    pass


class PacketType(Enum):
    """I3 packet types."""
    # Core services
    TELL = "tell"
    EMOTETO = "emoteto"
    CHANNEL_M = "channel-m"
    CHANNEL_E = "channel-e"
    CHANNEL_T = "channel-t"
    WHO_REQ = "who-req"
    WHO_REPLY = "who-reply"
    FINGER_REQ = "finger-req"
    FINGER_REPLY = "finger-reply"
    LOCATE_REQ = "locate-req"
    LOCATE_REPLY = "locate-reply"
    
    # Channel management
    CHANNEL_ADD = "channel-add"
    CHANNEL_REMOVE = "channel-remove"
    CHANNEL_ADMIN = "channel-admin"
    CHANNEL_FILTER = "channel-filter"
    CHANNEL_WHO = "channel-who"
    CHANNEL_LISTEN = "channel-listen"
    CHANLIST_REPLY = "chanlist-reply"
    
    # Router services
    STARTUP_REQ_3 = "startup-req-3"
    STARTUP_REPLY = "startup-reply"
    SHUTDOWN = "shutdown"
    MUDLIST = "mudlist"
    ERROR = "error"
    AUTH_MUD_REQ = "auth-mud-req"
    AUTH_MUD_REPLY = "auth-mud-reply"
    
    # OOB services
    OOB_REQ = "oob-req"
    OOB_BEGIN = "oob-begin"
    MAIL = "mail"
    MAIL_ACK = "mail-ack"
    NEWS = "news"
    NEWS_READ_REQ = "news-read-req"
    FILE = "file"


@dataclass
class I3Packet(ABC):
    """Base class for all I3 packets.
    
    All I3 packets follow this basic structure:
    [type, ttl, originator_mud, originator_user, target_mud, target_user, ...payload]
    """
    packet_type: PacketType
    ttl: int
    originator_mud: str
    originator_user: str
    target_mud: str
    target_user: str
    
    def __post_init__(self):
        """Validate packet after initialization."""
        self.validate()
    
    @abstractmethod
    def validate(self) -> None:
        """Validate packet structure and content.
        
        Raises:
            PacketValidationError: If validation fails
        """
        # Basic validation for all packets
        if self.ttl < 0 or self.ttl > 200:
            raise PacketValidationError(f"Invalid TTL: {self.ttl}")
        
        if not self.packet_type:
            raise PacketValidationError("Packet type is required")
    
    @abstractmethod
    def to_lpc_array(self) -> List[Any]:
        """Convert packet to LPC array format for transmission."""
        pass
    
    @classmethod
    @abstractmethod
    def from_lpc_array(cls, data: List[Any]) -> 'I3Packet':
        """Create packet from LPC array received from network."""
        pass
    
    def get_reply_packet(self, **kwargs) -> 'I3Packet':
        """Create a reply packet with swapped addresses.
        
        Args:
            **kwargs: Additional fields for the reply packet
            
        Returns:
            Reply packet with appropriate addressing
        """
        # Default implementation swaps originator and target
        reply_fields = {
            'ttl': 200,
            'originator_mud': self.target_mud,
            'originator_user': self.target_user,
            'target_mud': self.originator_mud,
            'target_user': self.originator_user,
        }
        reply_fields.update(kwargs)
        return self.__class__(**reply_fields)


@dataclass
class TellPacket(I3Packet):
    """Private message packet."""
    packet_type: PacketType = field(default=PacketType.TELL, init=False)
    message: str = ""
    
    def validate(self) -> None:
        """Validate tell packet."""
        super().validate()
        
        if not self.originator_user:
            raise PacketValidationError("Tell requires originator user")
        
        if not self.target_user:
            raise PacketValidationError("Tell requires target user")
        
        if not self.message:
            raise PacketValidationError("Tell requires a message")
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        return [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
            self.message
        ]
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'TellPacket':
        """Create from LPC array."""
        if len(data) < 7:
            raise PacketValidationError(f"Invalid tell packet: expected 7+ fields, got {len(data)}")
        
        return cls(
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
            message=str(data[6]) if data[6] else ""
        )


@dataclass
class ChannelPacket(I3Packet):
    """Channel message packet (supports channel-m, channel-e, channel-t)."""
    channel: str = ""
    message: str = ""
    
    def validate(self) -> None:
        """Validate channel packet."""
        super().validate()
        
        if not self.channel:
            raise PacketValidationError("Channel name is required")
        
        if not self.message:
            raise PacketValidationError("Channel message is required")
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        return [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
            self.channel,
            self.message
        ]
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'ChannelPacket':
        """Create from LPC array."""
        if len(data) < 8:
            raise PacketValidationError(f"Invalid channel packet: expected 8+ fields, got {len(data)}")
        
        # Determine packet type from data
        packet_type_str = str(data[0]) if data[0] else ""
        try:
            packet_type = PacketType(packet_type_str)
        except ValueError:
            packet_type = PacketType.CHANNEL_M  # Default
        
        return cls(
            packet_type=packet_type,
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
            channel=str(data[6]) if data[6] else "",
            message=str(data[7]) if data[7] else ""
        )


@dataclass
class WhoPacket(I3Packet):
    """Who request/reply packet."""
    # For who-req
    filter_criteria: Optional[Dict[str, Any]] = None
    
    # For who-reply
    who_data: Optional[List[Dict[str, Any]]] = None
    
    def validate(self) -> None:
        """Validate who packet."""
        super().validate()
        
        if self.packet_type == PacketType.WHO_REQ:
            # who-req can have optional filter criteria
            pass
        elif self.packet_type == PacketType.WHO_REPLY:
            if self.who_data is None:
                raise PacketValidationError("Who reply requires who_data")
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        base = [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
        ]
        
        if self.packet_type == PacketType.WHO_REQ:
            base.append(self.filter_criteria or {})
        else:
            base.append(self.who_data or [])
        
        return base
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'WhoPacket':
        """Create from LPC array."""
        if len(data) < 7:
            raise PacketValidationError(f"Invalid who packet: expected 7+ fields, got {len(data)}")
        
        packet_type_str = str(data[0]) if data[0] else ""
        packet_type = PacketType(packet_type_str)
        
        packet = cls(
            packet_type=packet_type,
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
        )
        
        if packet_type == PacketType.WHO_REQ and len(data) > 6:
            packet.filter_criteria = data[6] if isinstance(data[6], dict) else {}
        elif packet_type == PacketType.WHO_REPLY and len(data) > 6:
            packet.who_data = data[6] if isinstance(data[6], list) else []
        
        return packet


@dataclass
class FingerPacket(I3Packet):
    """Finger request/reply packet."""
    # For finger-req
    username: str = ""
    
    # For finger-reply
    user_info: Optional[Dict[str, Any]] = None
    
    def validate(self) -> None:
        """Validate finger packet."""
        super().validate()
        
        if self.packet_type == PacketType.FINGER_REQ:
            if not self.username:
                raise PacketValidationError("Finger request requires username")
        elif self.packet_type == PacketType.FINGER_REPLY:
            if self.user_info is None:
                raise PacketValidationError("Finger reply requires user_info")
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        base = [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
        ]
        
        if self.packet_type == PacketType.FINGER_REQ:
            base.append(self.username)
        else:
            base.append(self.user_info or {})
        
        return base
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'FingerPacket':
        """Create from LPC array."""
        if len(data) < 7:
            raise PacketValidationError(f"Invalid finger packet: expected 7+ fields, got {len(data)}")
        
        packet_type_str = str(data[0]) if data[0] else ""
        packet_type = PacketType(packet_type_str)
        
        packet = cls(
            packet_type=packet_type,
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
        )
        
        if packet_type == PacketType.FINGER_REQ and len(data) > 6:
            packet.username = str(data[6]) if data[6] else ""
        elif packet_type == PacketType.FINGER_REPLY and len(data) > 6:
            packet.user_info = data[6] if isinstance(data[6], dict) else {}
        
        return packet


@dataclass
class StartupPacket(I3Packet):
    """Startup request packet for router connection."""
    packet_type: PacketType = field(default=PacketType.STARTUP_REQ_3, init=False)
    
    password: int = 0
    mud_port: int = 0
    tcp_port: int = 0
    udp_port: int = 0
    mudlib: str = ""
    base_mudlib: str = ""
    driver: str = ""
    mud_type: str = ""
    open_status: str = ""
    admin_email: str = ""
    services: Dict[str, int] = field(default_factory=dict)
    other_data: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate startup packet."""
        super().validate()
        
        if not self.originator_mud:
            raise PacketValidationError("Startup requires originator MUD name")
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        return [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
            self.password,
            self.mud_port,
            self.tcp_port,
            self.udp_port,
            self.mudlib,
            self.base_mudlib,
            self.driver,
            self.mud_type,
            self.open_status,
            self.admin_email,
            self.services,
            self.other_data
        ]
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'StartupPacket':
        """Create from LPC array."""
        if len(data) < 18:
            raise PacketValidationError(f"Invalid startup packet: expected 18+ fields, got {len(data)}")
        
        return cls(
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
            password=int(data[6]) if data[6] else 0,
            mud_port=int(data[7]) if data[7] else 0,
            tcp_port=int(data[8]) if data[8] else 0,
            udp_port=int(data[9]) if data[9] else 0,
            mudlib=str(data[10]) if data[10] else "",
            base_mudlib=str(data[11]) if data[11] else "",
            driver=str(data[12]) if data[12] else "",
            mud_type=str(data[13]) if data[13] else "",
            open_status=str(data[14]) if data[14] else "",
            admin_email=str(data[15]) if data[15] else "",
            services=data[16] if isinstance(data[16], dict) else {},
            other_data=data[17] if isinstance(data[17], dict) else {}
        )


@dataclass
class MudlistPacket(I3Packet):
    """Mudlist update packet from router."""
    packet_type: PacketType = field(default=PacketType.MUDLIST, init=False)
    
    mudlist_id: int = 0
    mudlist: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate mudlist packet."""
        super().validate()
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        return [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
            self.mudlist_id,
            self.mudlist
        ]
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'MudlistPacket':
        """Create from LPC array."""
        if len(data) < 8:
            raise PacketValidationError(f"Invalid mudlist packet: expected 8+ fields, got {len(data)}")
        
        return cls(
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
            mudlist_id=int(data[6]) if data[6] else 0,
            mudlist=data[7] if isinstance(data[7], dict) else {}
        )


@dataclass
class ErrorPacket(I3Packet):
    """Error packet for protocol errors."""
    packet_type: PacketType = field(default=PacketType.ERROR, init=False)
    
    error_code: str = ""
    error_message: str = ""
    bad_packet: Optional[List[Any]] = None
    
    def validate(self) -> None:
        """Validate error packet."""
        super().validate()
        
        if not self.error_code:
            raise PacketValidationError("Error packet requires error code")
    
    def to_lpc_array(self) -> List[Any]:
        """Convert to LPC array."""
        return [
            self.packet_type.value,
            self.ttl,
            self.originator_mud,
            self.originator_user,
            self.target_mud,
            self.target_user,
            self.error_code,
            self.error_message,
            self.bad_packet or []
        ]
    
    @classmethod
    def from_lpc_array(cls, data: List[Any]) -> 'ErrorPacket':
        """Create from LPC array."""
        if len(data) < 9:
            raise PacketValidationError(f"Invalid error packet: expected 9+ fields, got {len(data)}")
        
        return cls(
            ttl=int(data[1]) if data[1] else 0,
            originator_mud=str(data[2]) if data[2] else "",
            originator_user=str(data[3]) if data[3] else "",
            target_mud=str(data[4]) if data[4] else "",
            target_user=str(data[5]) if data[5] else "",
            error_code=str(data[6]) if data[6] else "",
            error_message=str(data[7]) if data[7] else "",
            bad_packet=data[8] if isinstance(data[8], list) else None
        )


class PacketFactory:
    """Factory for creating I3 packets from raw data."""
    
    # Map packet type strings to packet classes
    _packet_classes: Dict[str, Type[I3Packet]] = {
        PacketType.TELL.value: TellPacket,
        PacketType.EMOTETO.value: TellPacket,  # Similar structure
        PacketType.CHANNEL_M.value: ChannelPacket,
        PacketType.CHANNEL_E.value: ChannelPacket,
        PacketType.CHANNEL_T.value: ChannelPacket,
        PacketType.WHO_REQ.value: WhoPacket,
        PacketType.WHO_REPLY.value: WhoPacket,
        PacketType.FINGER_REQ.value: FingerPacket,
        PacketType.FINGER_REPLY.value: FingerPacket,
        PacketType.STARTUP_REQ_3.value: StartupPacket,
        PacketType.MUDLIST.value: MudlistPacket,
        PacketType.ERROR.value: ErrorPacket,
    }
    
    @classmethod
    def create_packet(cls, data: List[Any]) -> I3Packet:
        """Create appropriate packet type from LPC array data.
        
        Args:
            data: LPC array data
            
        Returns:
            Appropriate I3Packet subclass instance
            
        Raises:
            PacketValidationError: If packet type is unknown or data is invalid
        """
        if not data or len(data) < 6:
            raise PacketValidationError(f"Invalid packet data: expected 6+ fields, got {len(data)}")
        
        packet_type_str = str(data[0]) if data[0] else ""
        
        packet_class = cls._packet_classes.get(packet_type_str)
        if not packet_class:
            # Return generic packet for unknown types
            # In production, might want to handle this differently
            raise PacketValidationError(f"Unknown packet type: {packet_type_str}")
        
        return packet_class.from_lpc_array(data)
    
    @classmethod
    def register_packet_class(cls, packet_type: str, packet_class: Type[I3Packet]):
        """Register a custom packet class.
        
        Args:
            packet_type: Packet type string
            packet_class: Packet class to register
        """
        cls._packet_classes[packet_type] = packet_class