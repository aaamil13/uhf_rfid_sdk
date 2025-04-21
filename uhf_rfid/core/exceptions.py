# uhf_rfid_async/uhf_rfid_async/core/exceptions.py

"""Custom exceptions for the uhf_rfid_async library."""

import asyncio # Needed for potential asyncio-specific exceptions
from typing import Optional
# --- Import constants ---
# Instead of defining CPH_STATUS_MESSAGES here, we import it
from uhf_rfid.protocols.cph import constants as cph_const


class UhfRfidError(Exception):
    """Base exception class for all uhf_rfid_async errors."""
    def __init__(self, message="An unspecified RFID error occurred."):
        super().__init__(message)


# --- Transport Layer Exceptions ---

class TransportError(UhfRfidError):
    """
    Base exception for errors related to the communication transport layer
    (Serial, TCP, UDP, Mock). It often wraps a lower-level exception.
    """
    def __init__(self, message="Transport layer error.", original_exception: Exception | None = None):
        """
        Args:
            message: A description of the transport error.
            original_exception: The underlying exception that caused this error (e.g., from pyserial-asyncio, asyncio streams).
        """
        super().__init__(message)
        self.original_exception = original_exception

    def __str__(self):
        base_msg = super().__str__()
        if self.original_exception:
            # Provide class name and message of the original exception
            orig_exc_type = type(self.original_exception).__name__
            orig_exc_msg = str(self.original_exception)
            return f"{base_msg} Original exception: [{orig_exc_type}] {orig_exc_msg}"
        return base_msg

class ConnectionError(TransportError):
    """
    Exception raised when establishing a connection fails.
    This is more specific than a general TransportError during an active connection.
    """
    def __init__(self, message="Failed to establish connection.", original_exception: Exception | None = None):
        super().__init__(message, original_exception)


class SerialConnectionError(ConnectionError):
    """
    Specific connection error related to Serial transport.
    Common reasons include:
    - Port does not exist.
    - Insufficient permissions to access the port.
    - Port is already in use by another application.
    - Device not physically connected or powered on.
    """
    def __init__(self, port: str | None = None, message="Serial connection error.", original_exception: Exception | None = None):
        msg = f"Serial connection error"
        if port:
            msg += f" on port '{port}'"
        msg += f": {message}"
        super().__init__(msg, original_exception)
        self.port = port


class NetworkConnectionError(ConnectionError):
    """
    Specific connection error related to TCP or UDP transport.
    Common reasons include:
    - Host unreachable (network configuration issue, firewall).
    - Connection refused (no service listening on the target port, firewall).
    - DNS resolution failed (invalid hostname).
    - Network interface down.
    """
    def __init__(self, host: str | None = None, port: int | None = None, message="Network connection error.", original_exception: Exception | None = None):
        msg = f"Network connection error"
        if host and port:
            msg += f" to {host}:{port}"
        elif host:
             msg += f" to host '{host}'"
        msg += f": {message}"
        super().__init__(msg, original_exception)
        self.host = host
        self.port = port


class ReadError(TransportError):
    """Exception raised when reading data from the transport fails unexpectedly."""
    def __init__(self, message="Failed to read data from transport.", original_exception: Exception | None = None):
        super().__init__(message, original_exception)


class WriteError(TransportError):
    """Exception raised when writing data to the transport fails unexpectedly."""
    def __init__(self, message="Failed to write data to transport.", original_exception: Exception | None = None):
        super().__init__(message, original_exception)


class TimeoutError(TransportError):
    """
    Exception raised when an expected operation (like receiving a response)
    does not complete within the allocated time. This often indicates a
    communication breakdown or a non-responsive reader.
    """
    def __init__(self, message="Operation timed out waiting for reader response."):
        # Inheriting from TransportError as timeouts often stem from comms issues.
        # Pass original_exception=None as it's usually generated internally by the library logic,
        # unless it directly wraps an asyncio.TimeoutError.
        super().__init__(message, original_exception=None)


# --- Protocol Layer Exceptions ---

class ProtocolError(UhfRfidError):
    """Exception related to protocol framing, parsing, or validation."""
    def __init__(self, message="Protocol error."):
        super().__init__(message)


class ChecksumError(ProtocolError):
    """Exception raised when frame checksum validation fails."""
    def __init__(self, calculated_checksum: int, received_checksum: int, frame: bytes):
        message = (
            f"Checksum mismatch. Calculated: 0x{calculated_checksum:02X}, "
            f"Received: 0x{received_checksum:02X}."
            # Limit frame length in message for readability
            f" Frame (hex): {frame[:32].hex(' ').upper()}{'...' if len(frame)>32 else ''}"
        )
        super().__init__(message)
        self.calculated_checksum = calculated_checksum
        self.received_checksum = received_checksum
        self.frame = frame


class FrameParseError(ProtocolError):
    """Exception raised during the parsing of a received frame's structure."""
    def __init__(self, message="Failed to parse frame structure.", frame_part: bytes | None = None):
        msg = f"Frame parsing error: {message}"
        if frame_part:
            msg += f" Near bytes: {frame_part[:32].hex(' ').upper()}{'...' if len(frame_part)>32 else ''}"
        super().__init__(msg)
        self.frame_part = frame_part


class TLVParseError(ProtocolError):
    """Exception raised during the parsing of TLV structures within a frame."""
    def __init__(self, message="Failed to parse TLV structure.", tlv_data: bytes | None = None):
        msg = f"TLV parsing error: {message}"
        if tlv_data:
            msg += f" Near bytes: {tlv_data[:32].hex(' ').upper()}{'...' if len(tlv_data)>32 else ''}"
        super().__init__(msg)
        self.tlv_data = tlv_data


# --- Command/Reader Logic Exceptions ---

class CommandError(UhfRfidError):
    """
    Exception representing an error reported by the reader in a response frame's
    status code, OR an error during command encoding/decoding.
    """
    def __init__(self, status_code: Optional[int] = None, frame: Optional[bytes] = None, message: Optional[str] = None):
        self.status_code = status_code
        self.frame = frame
        self.error_message = "Unknown error"

        final_message: str
        if message:
            # If a specific message is provided (e.g., for encoding/decoding errors)
            final_message = message
        elif status_code is not None:
            # If status code is provided, generate message from it
            self.error_message = cph_const.CPH_STATUS_MESSAGES.get(
                status_code,
                f"Unknown reader status code: 0x{status_code:02X}"
            )
            # Prepend "Reader Error:" to distinguish from library errors
            final_message = f"Reader Error (0x{status_code:02X}): {self.error_message}"
        else:
            # Fallback if neither message nor status_code is given
            final_message = "Command execution failed with unspecified error."

        super().__init__(final_message)

    def __str__(self):
        base_message = super().__str__()
        if self.frame:
             # Limit frame length in message for readability
            return f"{base_message} Frame (hex): {self.frame[:32].hex(' ').upper()}{'...' if len(self.frame)>32 else ''}"
        return base_message

class UnexpectedResponseError(ProtocolError):
    """
    Exception raised when the received response frame type or code
    does not match the expected response for the sent command.
    """
    def __init__(self, message="Received unexpected response from reader.", request_frame: bytes | None = None, response_frame: bytes | None = None):
        super().__init__(message)
        self.request_frame = request_frame
        self.response_frame = response_frame

    def __str__(self):
        base_msg = super().__str__()
        details = []
        if self.request_frame:
            details.append(f"Request: {self.request_frame[:32].hex(' ').upper()}{'...' if len(self.request_frame)>32 else ''}")
        if self.response_frame:
            details.append(f"Response: {self.response_frame[:32].hex(' ').upper()}{'...' if len(self.response_frame)>32 else ''}")
        if details:
            return f"{base_msg} ({'; '.join(details)})"
        return base_msg


# Example usage scenarios:
# try:
#     # Attempt serial connection
# except serial.SerialException as e:
#     raise SerialConnectionError(port=port, message="Could not open port.", original_exception=e)
#
# try:
#     # Attempt TCP connection
# except OSError as e: # Catches ConnectionRefusedError, HostUnreachableError etc.
#     raise NetworkConnectionError(host=host, port=port, message="OS error during connection.", original_exception=e)
# except asyncio.TimeoutError as e:
#      raise NetworkConnectionError(host=host, port=port, message="Connection attempt timed out.", original_exception=e)
#
# try:
#     # Reading data
#     reader.read(...)
# except asyncio.IncompleteReadError as e:
#     raise ReadError("Incomplete data received.", original_exception=e)
# except Exception as e: # Catch other potential read errors
#     raise ReadError("General read failure.", original_exception=e)
#
# # Inside frame parsing logic:
# if calculated_checksum != received_checksum:
#     raise ChecksumError(calculated_checksum, received_checksum, raw_frame)
# if header != b'RF':
#      raise FrameParseError("Invalid frame header", frame_part=raw_frame[:2])
#
# # Inside response handling:
# if response_status_code != 0x00:
#     raise CommandError(status_code=response_status_code, frame=response_frame)
# if received_frame_code != expected_frame_code:
#      raise UnexpectedResponseError(request_frame=sent_command_frame, response_frame=received_frame)