# uhf_rfid/transport/serial_async.py

import asyncio
import logging
from typing import Optional, Any, Dict

from uhf_rfid.core.status import ConnectionStatus

# Requires pyserial-asyncio: pip install pyserial-asyncio
try:
    import serial_asyncio
    import serial # For SerialException
except ImportError:
    serial_asyncio = None # Indicate missing dependency
    SerialException = Exception # Placeholder if serial isn't installed

from uhf_rfid.transport.base import BaseTransport, AsyncDataCallback # Use correct path
from uhf_rfid.core.exceptions import TransportError, ConnectionError, SerialConnectionError, ReadError, WriteError # Use correct path

logger = logging.getLogger(__name__)

DEFAULT_SERIAL_SETTINGS = {
    'baudrate': 115200,
    'bytesize': serial.EIGHTBITS if serial_asyncio else 8,
    'parity': serial.PARITY_NONE if serial_asyncio else 'N',
    'stopbits': serial.STOPBITS_ONE if serial_asyncio else 1,
    'timeout': None, # Must be None for async operation
    'xonxoff': False,
    'rtscts': False,
    'dsrdtr': False,
}

class SerialTransport(BaseTransport):
    """
    Asynchronous serial communication transport using pyserial-asyncio.
    """

    def __init__(self, connection_details: Dict[str, Any]):
        """
        Initializes the Serial Transport.

        Args:
            connection_details: Dictionary containing serial port settings.
                Required: 'port' (e.g., '/dev/ttyUSB0', 'COM3')
                Optional: 'baudrate', 'bytesize', 'parity', 'stopbits', etc.
                          Defaults are taken from DEFAULT_SERIAL_SETTINGS.
        """
        if serial_asyncio is None:
            raise ImportError("SerialTransport requires 'pyserial-asyncio' to be installed (`pip install pyserial-asyncio`).")

        super().__init__(connection_details)

        if 'port' not in self._connection_details:
            raise ValueError("Missing 'port' in connection_details for SerialTransport.")

        # Merge provided settings with defaults
        self._serial_settings = DEFAULT_SERIAL_SETTINGS.copy()
        self._serial_settings.update(self._connection_details)
        # Ensure timeout is None for async
        self._serial_settings['timeout'] = None

        self._port = self._serial_settings['port']
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        logger.info(f"SerialTransport initialized for port {self._port} with settings: {self._serial_settings}")

    async def connect(self) -> None:
        """Establishes the asynchronous serial connection."""
        async with self._connection_lock:
            if self._connected:
                logger.warning(f"Serial port {self._port} already connected.")
                return

            logger.info(f"Connecting to serial port {self._port}...")
            try:
                # --- START CORRECTION ---
                # Create a copy of settings without the 'port' key for unpacking
                settings_for_open = self._serial_settings.copy()
                if 'port' in settings_for_open: # Should always be true based on __init__
                    del settings_for_open['port']
                # Ensure 'url' isn't accidentally in the settings dict either
                if 'url' in settings_for_open:
                     del settings_for_open['url']

                # Pass port via 'url', other settings via **
                self._reader, self._writer = await serial_asyncio.open_serial_connection(
                    url=self._port, **settings_for_open # Use the modified settings dict
                )
                # --- END CORRECTION ---

                self._connected = True
                logger.info(f"Serial port {self._port} connected successfully.")

                # Start the background reader task now that connection is established
                await self._start_reader()

            except serial.SerialException as e:
                logger.error(f"Failed to connect to serial port {self._port}: {e}")
                self._connected = False
                self._reader = None
                self._writer = None
                 # Wrap the specific serial error
                raise SerialConnectionError(port=self._port, message=str(e), original_exception=e) from e
            except Exception as e: # Catch other potential errors like OSError
                 logger.error(f"Unexpected error connecting to {self._port}: {e}")
                 self._connected = False
                 self._reader = None
                 self._writer = None
                 raise ConnectionError(f"Unexpected error connecting to {self._port}: {e}", original_exception=e) from e


    async def disconnect(self) -> None:
        """Closes the asynchronous serial connection."""
        async with self._connection_lock:
            if not self._connected and not (self._reader_task and not self._reader_task.done()):
                # logger.debug(f"Serial port {self._port} already disconnected.")
                return

            logger.info(f"Disconnecting from serial port {self._port}...")

            # Stop the reader task first to prevent read errors during close
            await self._stop_reader()

            writer = self._writer # Local reference
            if writer:
                self._writer = None # Clear instance variable early
                self._reader = None
                if not writer.is_closing():
                    try:
                        writer.close()
                        # wait_closed() ensures the underlying transport is closed.
                        await writer.wait_closed()
                        logger.debug(f"Serial writer for {self._port} closed.")
                    except Exception as e:
                        # Log errors during close but continue disconnect process
                        logger.error(f"Error closing serial writer for {self._port}: {e}")
                        # Fall through to set _connected = False

            self._connected = False # Mark as disconnected regardless of close errors
            logger.info(f"Serial port {self._port} disconnected.")


    async def send(self, data: bytes) -> None:
        """Sends data over the serial port asynchronously."""
        if not self.is_connected() or not self._writer:
            raise TransportError(f"Cannot send data: Serial port {self._port} not connected or writer is invalid.")

        logger.debug(f"Serial sending ({len(data)} bytes) on {self._port}: {data.hex(' ').upper()}")
        try:
            self._writer.write(data)
            await self._writer.drain() # Wait until the buffer is flushed
            logger.debug(f"Serial send on {self._port} complete.")
        except ConnectionResetError as e:
             logger.error(f"Connection reset while writing to {self._port}: {e}")
             await self._update_status_and_disconnect(ConnectionStatus.ERROR) # Helper needed for this
             raise WriteError(f"Connection reset during send on {self._port}", original_exception=e) from e
        except Exception as e: # Catch potential OS errors, etc.
            logger.error(f"Failed to write to serial port {self._port}: {e}")
            # Consider the connection potentially broken
            # await self._update_status_and_disconnect(ConnectionStatus.ERROR)
            raise WriteError(f"Failed to write to serial port {self._port}", original_exception=e) from e

    async def _read_data_loop(self) -> None:
        """Background task to continuously read data from the serial port."""
        logger.info(f"Serial reader loop started for {self._port}.")
        try:
            while self._connected and self._reader:
                # Read up to a certain number of bytes. Adjust buffer size if needed.
                # A smaller size might be more responsive but less efficient.
                # read() waits until at least one byte is received.
                data = await self._reader.read(4096)

                if data:
                    logger.debug(f"Serial received ({len(data)} bytes) on {self._port}: {data.hex(' ').upper()}")
                    if self._data_received_callback:
                        try:
                            await self._data_received_callback(data)
                        except Exception as e:
                             logger.exception(f"Error in serial data received callback: {e}")
                    else:
                        logger.warning(f"Serial data received on {self._port} but no callback registered.")
                else:
                    # read() returning empty bytes usually means EOF or connection closed
                    logger.warning(f"Serial port {self._port} read returned empty data. Assuming connection closed remotely.")
                    # Mark as disconnected and break loop
                    if self._connected: # Avoid duplicate disconnect calls if disconnect() was called concurrently
                         # Trigger a disconnect from the read loop side
                         asyncio.create_task(self._handle_remote_disconnect())
                    break

        except asyncio.CancelledError:
            logger.info(f"Serial reader loop for {self._port} cancelled.")
            # Propagate cancellation if needed
            raise
        except serial.SerialException as e:
            logger.error(f"Serial error during read on {self._port}: {e}")
            if self._connected:
                 asyncio.create_task(self._handle_read_error(e))
            # Let loop terminate
        except ConnectionResetError as e:
             logger.error(f"Connection reset while reading from {self._port}: {e}")
             if self._connected:
                  asyncio.create_task(self._handle_read_error(e))
        except Exception as e:
            logger.exception(f"Unexpected error in serial reader loop for {self._port}: {e}")
            if self._connected:
                 asyncio.create_task(self._handle_read_error(e))
             # Let loop terminate
        finally:
            logger.info(f"Serial reader loop for {self._port} stopped.")
            # Ensure disconnect state is reflected if loop exits unexpectedly while _connected=True
            # if self._connected:
            #     logger.warning(f"Reader loop for {self._port} exited unexpectedly while still marked connected. Forcing disconnect.")
            #     asyncio.create_task(self.disconnect()) # Ensure disconnect is called

    async def _handle_remote_disconnect(self):
        """Handle case where remote end closes connection."""
        logger.warning(f"Handling remote disconnect detected on {self._port}.")
        # Avoid race conditions with explicit disconnect calls
        if self._connected and self._status != ConnectionStatus.DISCONNECTING:
            await self._update_status(ConnectionStatus.ERROR) # Or maybe just DISCONNECTED? ERROR seems appropriate
            await self.disconnect() # Trigger the full disconnect sequence

    async def _handle_read_error(self, error: Exception):
         """Handle read errors detected in the loop."""
         logger.error(f"Handling read error detected on {self._port}: {error}")
         if self._connected and self._status != ConnectionStatus.DISCONNECTING:
              await self._update_status(ConnectionStatus.ERROR)
              await self.disconnect() # Assume connection is broken


    # Helper to link transport error back to Reader's status (needs Reader instance or callback)
    # This is slightly awkward as transport shouldn't know about Reader directly.
    # A status callback passed to Transport might be cleaner. For now, omit direct status update from here.
    # async def _update_status_and_disconnect(self, status: ConnectionStatus):
    #     logger.error(f"Critical transport error on {self._port}. Setting status to {status} and disconnecting.")
    #     # How to signal Reader? Event? Callback?
    #     # For now, just disconnect
    #     if self._connected:
    #         await self.disconnect()