# uhf_rfid/transport/base.py

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, Coroutine, Any # Added for type hints

from uhf_rfid.core.exceptions import TransportError

# Define a type hint for the asynchronous data callback
# The callback will receive bytes and should be an async function
AsyncDataCallback = Callable[[bytes], Coroutine[Any, Any, None]]

class BaseTransport(ABC):
    """
    Abstract base class for all communication transport layers.

    Defines the common interface for connecting, disconnecting, sending,
    and receiving data asynchronously. Concrete implementations handle
    the specifics of Serial, TCP, UDP, or Mock communication.
    """

    def __init__(self, connection_details: dict[str, Any]):
        """
        Initializes the transport base.

        Args:
            connection_details: A dictionary containing parameters needed to
                                establish the connection (e.g., {'port': '/dev/ttyUSB0', 'baudrate': 115200}
                                for serial, {'host': '192.168.1.100', 'port': 6000} for TCP/UDP).
        """
        self._connection_details = connection_details
        self._receive_buffer = bytearray()
        self._data_received_callback: Optional[AsyncDataCallback] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._connected = False
        self._connection_lock = asyncio.Lock() # Prevent race conditions during connect/disconnect

    @abstractmethod
    async def connect(self) -> None:
        """
        Establishes the connection to the reader device asynchronously.
        Must be implemented by subclasses.

        Raises:
            ConnectionError: If the connection cannot be established.
            TransportError: For other connection-related errors.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Closes the connection to the reader device asynchronously.
        Must be implemented by subclasses. Safe to call even if not connected.
        """
        pass

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """
        Sends data over the transport layer asynchronously.

        Args:
            data: The bytes to send.

        Raises:
            TransportError: If not connected or if writing fails.
            WriteError: If writing fails.
        """
        if not self.is_connected():
             # It's generally better to check connection status before calling send
             # in the Reader class, but this adds a layer of safety.
            raise TransportError("Cannot send data: Not connected.")
        pass # Implementation details in subclasses

    @abstractmethod
    async def _read_data_loop(self) -> None:
        """
        Internal loop that continuously reads data from the transport
        and calls the registered data callback.
        This method should be started as an asyncio Task by the connect() method.
        Must be implemented by subclasses.
        """
        pass

    def register_data_callback(self, callback: AsyncDataCallback) -> None:
        """
        Registers an asynchronous callback function to be called when data is received.

        Args:
            callback: An async function that takes bytes as an argument.
                      Example: async def my_callback(data: bytes): ...
        """
        if not asyncio.iscoroutinefunction(callback):
            raise TypeError("Callback must be an async function (defined with 'async def')")
        self._data_received_callback = callback
        print(f"Data callback registered: {callback.__name__}") # Debug print

    def unregister_data_callback(self) -> None:
        """Removes the registered data callback."""
        print(f"Unregistering data callback: {getattr(self._data_received_callback, '__name__', 'None')}") # Debug print
        self._data_received_callback = None

    def is_connected(self) -> bool:
        """Returns True if the transport layer is currently connected, False otherwise."""
        return self._connected

    async def _start_reader(self) -> None:
        """Starts the background reading task."""
        if self._reader_task is None or self._reader_task.done():
            print("Starting reader task...") # Debug print
            self._reader_task = asyncio.create_task(self._read_data_loop())
            # Add a shield or error handling if needed
        else:
             print("Reader task already running.") # Debug print


    async def _stop_reader(self) -> None:
        """Stops the background reading task gracefully."""
        if self._reader_task and not self._reader_task.done():
            print("Stopping reader task...") # Debug print
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                print("Reader task cancelled successfully.") # Debug print
            except Exception as e:
                # Log or handle other potential exceptions during task shutdown
                print(f"Error stopping reader task: {e}") # Debug print/log
            finally:
                self._reader_task = None
        else:
            print("Reader task not running or already stopped.") # Debug print

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    @property
    def connection_details(self) -> dict[str, Any]:
        """Returns the connection details provided during initialization."""
        return self._connection_details