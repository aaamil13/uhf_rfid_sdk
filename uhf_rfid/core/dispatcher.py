# uhf_rfid/core/dispatcher.py

import asyncio
import logging
from typing import Optional, Callable, Any, Dict, Tuple, Coroutine, List
from collections import deque, defaultdict

from uhf_rfid.transport.base import BaseTransport, AsyncDataCallback
from uhf_rfid.protocols.base_protocol import BaseProtocol
from uhf_rfid.protocols import framing
from uhf_rfid.core.exceptions import UhfRfidError, ProtocolError, CommandError, ChecksumError, FrameParseError, \
    TimeoutError, UnexpectedResponseError, TransportError
from uhf_rfid.protocols.cph import constants as cph_const

# Type hint for notification callbacks
# Callback receives: frame_type, address, frame_code, parsed_params
NotificationCallback = Callable[[int, int, int, Any], Coroutine[Any, Any, None]]

DEFAULT_RESPONSE_TIMEOUT = 2.0 # Seconds to wait for a command response

logger = logging.getLogger(__name__) # Use logging

class Dispatcher:
    """
    Handles incoming data, parses frames, matches responses to commands,
    and invokes notification callbacks.
    """

    def __init__(self, transport: BaseTransport, protocol: BaseProtocol, response_timeout: float = DEFAULT_RESPONSE_TIMEOUT):
        self._transport = transport
        self._protocol = protocol
        self._response_timeout = response_timeout

        self._rx_buffer = bytearray()
        self._transport.register_data_callback(self._data_received_handler) # Register to get data

        # For matching responses to commands
        # Key: command_code (or maybe a unique transaction ID)
        # Value: asyncio.Future that the waiting command coroutine 'awaits'
        self._pending_responses: Dict[int, asyncio.Future] = {}
        self._response_lock = asyncio.Lock() # Protect access to _pending_responses

        # For notification callbacks (e.g., tag reads)
        # CHANGE: Use a dictionary mapping frame_code to a list of callbacks
        self._notification_callbacks: Dict[int, List[NotificationCallback]] = defaultdict(list)
        self._callback_lock = asyncio.Lock() # Protect access to callbacks dict

    async def _data_received_handler(self, data: bytes) -> None:
        """Async callback called by the transport layer when data arrives."""
        logger.debug(f"Received {len(data)} bytes: {data.hex(' ').upper()}")
        self._rx_buffer.extend(data)
        await self._process_buffer()

    async def _process_buffer(self) -> None:
        """Continuously tries to parse complete frames from the buffer."""
        while True:
            parsed_frame_data = framing.find_and_parse_frame(self._rx_buffer)

            if parsed_frame_data is None:
                # No complete, valid frame found in the buffer currently.
                # Wait for more data (handled by subsequent calls to _data_received_handler)
                # Log if buffer gets excessively large?
                if len(self._rx_buffer) > 4096: # Example threshold
                     logger.warning(f"Receive buffer size exceeds {len(self._rx_buffer)} bytes. Potential sync issue or large data.")
                break # Exit the loop for now

            # A valid frame was found and buffer was consumed
            frame_type, address, frame_code, params_data, frame_len = parsed_frame_data
            logger.debug(f"Parsed frame: Type=0x{frame_type:02X}, Addr=0x{address:04X}, Code=0x{frame_code:02X}, Len={frame_len}, Params={params_data.hex(' ').upper()}")

            try:
                # Now parse the parameters using the protocol logic
                parsed_params = self._protocol.parse_parameters(frame_code, frame_type, params_data)
                logger.debug(f"Parsed params: {parsed_params}")

                # Route the frame based on its type
                if frame_type == cph_const.FRAME_TYPE_RESPONSE:
                    await self._handle_response(address, frame_code, parsed_params, params_data) # Pass raw params too for CommandError
                elif frame_type == cph_const.FRAME_TYPE_NOTIFICATION:
                    await self._handle_notification(address, frame_code, parsed_params)
                elif frame_type == cph_const.FRAME_TYPE_COMMAND:
                    # Typically, a host doesn't receive commands, but log if it happens
                    logger.warning(f"Received unexpected COMMAND frame: Addr=0x{address:04X}, Code=0x{frame_code:02X}")
                else:
                    logger.warning(f"Received unknown frame type: 0x{frame_type:02X}")

            except (ProtocolError, ChecksumError, FrameParseError) as e:
                # Error during parameter parsing specifically
                logger.error(f"Error parsing parameters for frame (Type=0x{frame_type:02X}, Code=0x{frame_code:02X}): {e}")
                # Decide how to handle - maybe notify an error callback?
            except Exception as e:
                 logger.exception(f"Unexpected error processing parsed frame: {e}") # Log stack trace

            # Loop again immediately to check if another complete frame exists in the buffer

    async def _handle_response(self, address: int, frame_code: int, parsed_params: Any, raw_params: bytes) -> None:
        """Handles a received response frame."""
        future = None
        async with self._response_lock:
            future = self._pending_responses.pop(frame_code, None)

        if future and not future.done():
             # Check for error status in the response (assuming Status TLV is tag 0x07)
             status_code = None
             if isinstance(parsed_params, dict) and 0x07 in parsed_params:
                 status_data = parsed_params[0x07]
                 # Check if it's the parsed status code directly or needs extraction
                 if isinstance(status_data, int):
                     status_code = status_data
                 # Add more checks if status is nested differently

             if status_code is not None and status_code != 0x00: # 0x00 is SUCCESS
                 # Reader reported an error
                 logger.warning(f"Reader responded with error status 0x{status_code:02X} for command 0x{frame_code:02X}")
                 error = CommandError(status_code=status_code, frame=raw_params) # Pass raw frame bytes too
                 future.set_exception(error)
             else:
                 # Success or no status code found (assume success?)
                 logger.debug(f"Response received for command 0x{frame_code:02X}")
                 future.set_result(parsed_params) # Resolve the future with parsed data
        else:
            # No pending future found for this response code, or future already done (e.g., timed out)
            logger.warning(f"Received unexpected or late response for command 0x{frame_code:02X}: {parsed_params}")
            # Optionally, could route unexpected responses to a separate callback

    async def _handle_notification(self, address: int, frame_code: int, parsed_params: Any) -> None:
        """Handles a received notification frame by invoking callbacks."""
        #logger.info(f"Notification received: Addr=0x{address:04X}, Code=0x{frame_code:02X}, Params={parsed_params}")
        callbacks_to_run: List[NotificationCallback] = []
        async with self._callback_lock:
            # Get the list of callbacks registered specifically for this frame_code
            if frame_code in self._notification_callbacks:
                callbacks_to_run = list(self._notification_callbacks[frame_code]) # Create a copy to run outside the lock
            else:
                 logger.debug(f"No callbacks registered for notification code 0x{frame_code:02X}")

        if callbacks_to_run:
             logger.debug(f"Invoking {len(callbacks_to_run)} callbacks for notification 0x{frame_code:02X}")
             # Create tasks for all registered callbacks concurrently
             tasks = [
                 asyncio.create_task(cb(cph_const.FRAME_TYPE_NOTIFICATION, address, frame_code, parsed_params))
                 for cb in callbacks_to_run
             ]
             # Wait for all callback tasks to complete (or handle errors)
             # Use return_exceptions=True to log errors but not stop others
             results = await asyncio.gather(*tasks, return_exceptions=True)
             for i, result in enumerate(results):
                  if isinstance(result, Exception):
                       cb_name = getattr(callbacks_to_run[i], '__name__', repr(callbacks_to_run[i]))
                       logger.error(f"Error executing notification callback {cb_name} for code 0x{frame_code:02X}: {result}", exc_info=isinstance(result, Exception))

    async def send_command_wait_response(self, command_code: int, address: int = 0x0000, params_data: bytes = b'') -> Any:
        """
        Encodes, sends a command, and waits for a matching response.

        Args:
            command_code: The command code to send.
            address: The target device address.
            params_data: Pre-encoded parameters for the command.

        Returns:
            The parsed parameter data from the successful response frame.

        Raises:
            TimeoutError: If no response is received within the timeout period.
            CommandError: If the reader returns an error status code.
            TransportError: If sending fails.
            ProtocolError: If encoding fails.
            UnexpectedResponseError: Potentially if response code mismatch (though current logic uses command_code for matching).
        """
        if not self._transport.is_connected():
            raise TransportError("Cannot send command: Not connected.")

        future = asyncio.Future()
        async with self._response_lock:
            if command_code in self._pending_responses:
                # This shouldn't happen if commands are sent sequentially and awaited
                logger.error(f"Command collision: Already waiting for response to code 0x{command_code:02X}")
                # Handle this? Maybe raise an error or cancel previous?
                # For now, let's overwrite, assuming the previous one timed out or was lost.
                # A better approach might involve unique transaction IDs.
                old_future = self._pending_responses[command_code]
                if not old_future.done():
                    old_future.set_exception(TimeoutError(f"Superseded by new command 0x{command_code:02X}"))

            self._pending_responses[command_code] = future

        try:
            # Encode the command
            full_frame = self._protocol.encode_command(command_code, address, params_data)
            logger.debug(f"Sending command: Code=0x{command_code:02X}, Addr=0x{address:04X}, Frame={full_frame.hex(' ').upper()}")

            # Send the command
            await self._transport.send(full_frame)

            # Wait for the response future to be resolved or timeout
            logger.debug(f"Waiting for response to command 0x{command_code:02X} (timeout={self._response_timeout}s)")
            response_data = await asyncio.wait_for(future, timeout=self._response_timeout)
            logger.debug(f"Response received successfully for 0x{command_code:02X}")
            return response_data

        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response to command 0x{command_code:02X}")
            # Clean up the future from pending requests if it's still there
            async with self._response_lock:
                if command_code in self._pending_responses and self._pending_responses[command_code] is future:
                    del self._pending_responses[command_code]
            # Ensure future is cancelled if not already resolved/excepted
            if not future.done():
                 future.cancel("Timeout") # Set future to cancelled state
            raise TimeoutError(f"No response received for command 0x{command_code:02X} within {self._response_timeout}s") from None
        except UhfRfidError as e:
             # Catch library-specific errors (Transport, Protocol, CommandError set by _handle_response)
             logger.error(f"Error during command 0x{command_code:02X}: {e}")
             # Clean up future if it wasn't resolved/excepted properly
             async with self._response_lock:
                 if command_code in self._pending_responses and self._pending_responses[command_code] is future:
                     del self._pending_responses[command_code]
             if not future.done(): future.cancel(str(e))
             raise # Re-raise the caught exception
        except Exception as e:
             # Catch unexpected errors
             logger.exception(f"Unexpected error sending/waiting for command 0x{command_code:02X}: {e}")
             async with self._response_lock:
                 if command_code in self._pending_responses and self._pending_responses[command_code] is future:
                     del self._pending_responses[command_code]
             if not future.done(): future.cancel(str(e))
             raise UhfRfidError(f"Unexpected error during command 0x{command_code:02X}: {e}") from e


    async def register_notification_callback(self, frame_code: int, callback: NotificationCallback) -> None:
        """Registers an async callback for a specific notification frame code."""
        if not asyncio.iscoroutinefunction(callback):
            raise TypeError("Notification callback must be an async function (defined with 'async def')")
        async with self._callback_lock:
            # Add callback to the list for the specific frame_code
            # Using defaultdict avoids checking if key exists
            if callback not in self._notification_callbacks[frame_code]:
                self._notification_callbacks[frame_code].append(callback)
                logger.info(f"Registered callback {getattr(callback, '__name__', repr(callback))} for notification code 0x{frame_code:02X}")
            else:
                 logger.warning(f"Callback {getattr(callback, '__name__', repr(callback))} already registered for code 0x{frame_code:02X}")

    async def unregister_notification_callback(self, frame_code: int, callback: NotificationCallback) -> None:
        """Unregisters a notification callback for a specific frame code."""
        async with self._callback_lock:
            if frame_code in self._notification_callbacks:
                try:
                    self._notification_callbacks[frame_code].remove(callback)
                    logger.info(f"Unregistered callback {getattr(callback, '__name__', repr(callback))} for code 0x{frame_code:02X}")
                    # Optional: Remove the frame_code key if the list becomes empty
                    if not self._notification_callbacks[frame_code]:
                         del self._notification_callbacks[frame_code]
                except ValueError:
                    logger.warning(f"Callback {getattr(callback, '__name__', repr(callback))} not found for code 0x{frame_code:02X}")
            else:
                 logger.warning(f"No callbacks registered for code 0x{frame_code:02X} to unregister from.")

    async def unregister_callback_from_all(self, callback: NotificationCallback) -> None:
         """Unregisters a specific callback from all notification codes it might be registered for."""
         async with self._callback_lock:
              unregistered_count = 0
              codes_to_remove = []
              for frame_code, callback_list in self._notification_callbacks.items():
                   if callback in callback_list:
                        try:
                             callback_list.remove(callback)
                             logger.debug(f"Unregistered callback {getattr(callback, '__name__', repr(callback))} from code 0x{frame_code:02X}")
                             unregistered_count += 1
                             if not callback_list:
                                  codes_to_remove.append(frame_code)
                        except ValueError:
                             # Should not happen if `callback in callback_list` is true, but safety check
                             pass 
              # Remove empty lists outside the loop
              for code in codes_to_remove:
                   del self._notification_callbacks[code]
              if unregistered_count > 0:
                   logger.info(f"Unregistered callback {getattr(callback, '__name__', repr(callback))} from {unregistered_count} notification code(s).")
              else:
                   logger.warning(f"Callback {getattr(callback, '__name__', repr(callback))} was not found registered for any notification code.")


    def clear_buffer(self):
        """Manually clears the receive buffer."""
        logger.debug(f"Clearing receive buffer ({len(self._rx_buffer)} bytes)")
        self._rx_buffer.clear()

    async def cleanup(self) -> None:
        """Cleans up resources, like cancelling pending futures."""
        logger.debug("Dispatcher cleaning up...")
        async with self._response_lock:
            for code, future in self._pending_responses.items():
                if not future.done():
                    logger.warning(f"Cancelling pending response future for command 0x{code:02X} during cleanup.")
                    future.cancel("Dispatcher cleanup")
            self._pending_responses.clear()
        # No need to explicitly clear callbacks list, but good practice if needed elsewhere
        # async with self._callback_lock:
        #     self._notification_callbacks.clear()
        # Unregister from transport if necessary (though transport disconnect should handle it)
        # self._transport.unregister_data_callback() # Might cause issues if transport is reused
