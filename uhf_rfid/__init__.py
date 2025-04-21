"""UHF RFID Library - Asynchronous library for interacting with UHF RFID readers."""

from .core import (
    Reader,
    ConnectionStatus,
    UhfRfidError,
    CommandError,
    ProtocolError,
    TransportError,
    InvalidTagDataError,
    UnknownTagError
)
from .transport import (
    SerialTransport,
    TcpTransport,
    MockTransport,
    UdpTransport
)
from .protocols.cph import CPHProtocol

__version__ = '0.2.0'

__all__ = [
    # Core components
    'Reader',
    'ConnectionStatus',
    # Exceptions
    'UhfRfidError',
    'CommandError',
    'ProtocolError',
    'TransportError',
    'InvalidTagDataError',
    'UnknownTagError',
    # Transport
    'SerialTransport',
    'TcpTransport',
    'MockTransport',
    'UdpTransport',
    # Protocols
    'CPHProtocol',
] 