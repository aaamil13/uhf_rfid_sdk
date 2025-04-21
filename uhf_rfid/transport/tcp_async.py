# uhf_rfid/transport/tcp_async.py

import asyncio
import logging
from typing import Optional, Any, Dict

from uhf_rfid.transport.base import BaseTransport, AsyncDataCallback # Use correct path
from uhf_rfid.core.exceptions import TransportError, ConnectionError, NetworkConnectionError, ReadError, WriteError # Use correct path
from uhf_rfid.core.status import ConnectionStatus # Needed for status updates on error

logger = logging.getLogger(__name__)

DEFAULT_TCP_BUFFER_SIZE = 4096 # Bytes to read at a time

class TcpTransport(BaseTransport):
    """
    Asynchronous TCP communication transport using asyncio streams.
    """

    def __init__(self, connection_details: Dict[str, Any]):
        """
        Initializes the TCP Transport.

        Args:
            connection_details: Dictionary containing TCP connection settings.
                Required: 'host' (string, IP address or hostname)
                          'port' (integer)
        """
        super().__init__(connection_details)

        if 'host' not in self._connection_details or 'port' not in self._connection_details:
            raise ValueError("Missing 'host' or 'port' in connection_details for TcpTransport.")

        self._host = str(self._connection_details['host'])
        self._port = int(self._connection_details['port'])

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._read_buffer_size = self._connection_details.get('buffer_size', DEFAULT_TCP_BUFFER_SIZE)

        logger.info(f"TcpTransport initialized for {self._host}:{self._port}")

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def connect(self) -> None:
        """Establishes the asynchronous TCP connection."""
        async with self._connection_lock:
            if self._connected:
                logger.warning(f"TCP connection to {self.host}:{self.port} already established.")
                return

            logger.info(f"Connecting to TCP endpoint {self.host}:{self.port}...")
            try:
                # Use asyncio's stream API to open the connection
                self._reader, self._writer = await asyncio.open_connection(
                    host=self.host, port=self.port
                )
                self._connected = True
                peername = self._writer.get_extra_info('peername', ('Unknown', 'Unknown'))
                logger.info(f"TCP connection to {self.host}:{self.port} established (peer: {peername}).")

                # Start the background reader task
                await self._start_reader()

            except ConnectionRefusedError as e:
                logger.error(f"Connection refused when connecting to {self.host}:{self.port}: {e}")
                self._connected = False
                self._reader = None
                self._writer = None
                raise NetworkConnectionError(host=self.host, port=self.port, message="Connection refused.", original_exception=e) from e
            except asyncio.TimeoutError as e:
                 logger.error(f"Timeout during TCP connection attempt to {self.host}:{self.port}: {e}")
                 self._connected = False
                 self._reader = None
                 self._writer = None
                 raise NetworkConnectionError(host=self.host, port=self.port, message="Connection attempt timed out.", original_exception=e) from e
            except OSError as e: # Catches host unreachable, network errors etc.
                logger.error(f"OS error connecting to {self.host}:{self.port}: {e}")
                self._connected = False
                self._reader = None
                self._writer = None
                raise NetworkConnectionError(host=self.host, port=self.port, message=f"OS error: {e}", original_exception=e) from e
            except Exception as e: # Catch other unexpected errors
                 logger.exception(f"Unexpected error connecting to {self.host}:{self.port}: {e}")
                 self._connected = False
                 self._reader = None
                 self._writer = None
                 raise ConnectionError(f"Unexpected error connecting to {self.host}:{self.port}: {e}", original_exception=e) from e


    async def disconnect(self) -> None:
        """Closes the asynchronous TCP connection."""
        async with self._connection_lock:
            if not self._connected and not (self._reader_task and not self._reader_task.done()):
                # logger.debug(f"TCP connection to {self.host}:{self.port} already disconnected.")
                return

            logger.info(f"Disconnecting from TCP endpoint {self.host}:{self.port}...")

            # Stop the reader task first
            await self._stop_reader()

            writer = self._writer # Local reference
            if writer:
                self._writer = None # Clear instance variable early
                self._reader = None
                if not writer.is_closing():
                    try:
                        writer.close()
                        await writer.wait_closed()
                        logger.debug(f"TCP writer for {self.host}:{self.port} closed.")
                    except Exception as e:
                        logger.error(f"Error closing TCP writer for {self.host}:{self.port}: {e}")
                        # Continue disconnect anyway

            self._connected = False # Mark as disconnected
            logger.info(f"TCP connection to {self.host}:{self.port} disconnected.")


    async def send(self, data: bytes) -> None:
        """Sends data over the TCP connection asynchronously."""
        if not self.is_connected() or not self._writer:
            raise TransportError(f"Cannot send data: TCP connection to {self.host}:{self.port} not established or writer is invalid.")

        peername = self._writer.get_extra_info('peername', 'Unknown')
        logger.debug(f"TCP sending ({len(data)} bytes) to {peername}: {data.hex(' ').upper()}")
        try:
            self._writer.write(data)
            await self._writer.drain() # Wait until the OS buffer accepts all data
            logger.debug(f"TCP send to {peername} complete.")
        except (ConnectionResetError, BrokenPipeError) as e:
             logger.error(f"Connection error while writing to {self.host}:{self.port}: {e}")
             # Connection is likely broken, trigger disconnect
             if self._connected: # Avoid race conditions
                 asyncio.create_task(self._handle_write_error(e))
             raise WriteError(f"Connection error during send to {self.host}:{self.port}", original_exception=e) from e
        except OSError as e: # Other potential socket errors
             logger.error(f"OS error while writing to {self.host}:{self.port}: {e}")
             if self._connected:
                 asyncio.create_task(self._handle_write_error(e))
             raise WriteError(f"OS error during send to {self.host}:{self.port}", original_exception=e) from e
        except Exception as e:
             logger.exception(f"Unexpected error writing to {self.host}:{self.port}: {e}")
             if self._connected:
                 asyncio.create_task(self._handle_write_error(e))
             raise WriteError(f"Unexpected error during send to {self.host}:{self.port}", original_exception=e) from e


    async def _read_data_loop(self) -> None:
        """Background task to continuously read data from the TCP connection."""
        peername = self._writer.get_extra_info('peername', 'Unknown') if self._writer else 'Unknown'
        logger.info(f"TCP reader loop started for {peername}.")
        try:
            while self._connected and self._reader:
                # Read data from the stream
                data = await self._reader.read(self._read_buffer_size)

                if data:
                    logger.debug(f"TCP received ({len(data)} bytes) from {peername}: {data.hex(' ').upper()}")
                    if self._data_received_callback:
                        try:
                            await self._data_received_callback(data)
                        except Exception as e:
                             logger.exception(f"Error in TCP data received callback: {e}")
                    else:
                        logger.warning(f"TCP data received from {peername} but no callback registered.")
                else:
                    # read() returning empty bytes means EOF - connection closed by peer
                    logger.warning(f"TCP connection closed by peer {peername}.")
                    if self._connected: # Avoid duplicate disconnect calls
                         asyncio.create_task(self._handle_remote_disconnect())
                    break # Exit loop

        except asyncio.CancelledError:
            logger.info(f"TCP reader loop for {peername} cancelled.")
            raise
        except asyncio.IncompleteReadError as e:
             logger.error(f"Incomplete read from {peername}: {e}")
             if self._connected:
                  asyncio.create_task(self._handle_read_error(e))
        except (ConnectionResetError, BrokenPipeError) as e:
             logger.error(f"Connection error while reading from {peername}: {e}")
             if self._connected:
                  asyncio.create_task(self._handle_read_error(e))
        except OSError as e: # Other socket errors
             logger.error(f"OS error while reading from {peername}: {e}")
             if self._connected:
                  asyncio.create_task(self._handle_read_error(e))
        except Exception as e:
             logger.exception(f"Unexpected error in TCP reader loop for {peername}: {e}")
             if self._connected:
                  asyncio.create_task(self._handle_read_error(e))
        finally:
             logger.info(f"TCP reader loop for {peername} stopped.")


    # --- Error Handling Helpers (similar to SerialTransport) ---

    async def _handle_remote_disconnect(self):
        """Handle case where remote end closes connection."""
        peer = f"{self.host}:{self.port}" # Use configured host/port as peername might be unavailable
        logger.warning(f"Handling remote disconnect detected on {peer}.")
        # Check _connected and potentially Reader status via callback/event if implemented
        if self._connected: # Check internal flag first
            # Assume connection is broken, trigger full disconnect
            # Maybe notify Reader first? For now, just disconnect transport.
            await self.disconnect() # Let disconnect handle status updates

    async def _handle_read_error(self, error: Exception):
         """Handle read errors detected in the loop."""
         peer = f"{self.host}:{self.port}"
         logger.error(f"Handling read error detected on {peer}: {error}")
         if self._connected:
              # Assume connection is broken, trigger full disconnect
              await self.disconnect()

    async def _handle_write_error(self, error: Exception):
         """Handle write errors detected during send."""
         peer = f"{self.host}:{self.port}"
         logger.error(f"Handling write error detected on {peer}: {error}")
         if self._connected:
              # Assume connection is broken, trigger full disconnect
              await self.disconnect()
