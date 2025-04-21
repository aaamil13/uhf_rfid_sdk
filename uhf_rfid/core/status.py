# uhf_rfid/core/status.py

from enum import Enum, auto

class ConnectionStatus(Enum):
    """Represents the connection state of the reader."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    ERROR = auto() # Indicates an unrecoverable error state

    def __str__(self):
        # Provide a user-friendly string representation
        return self.name
