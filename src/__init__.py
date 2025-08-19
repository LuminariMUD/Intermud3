"""I3 Gateway - Intermud3 Protocol Gateway Service."""

__version__ = "0.1.0"
__author__ = "I3 Gateway Team"
__description__ = "A standalone Python service for MUD-to-I3 network bridging"

from typing import Final


# Protocol version constants
I3_PROTOCOL_VERSION: Final[int] = 3
MUDMODE_VERSION: Final[int] = 1

# Service identifier
SERVICE_NAME: Final[str] = "i3-gateway"
