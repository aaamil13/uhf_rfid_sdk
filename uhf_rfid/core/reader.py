# uhf_rfid/core/reader.py

import asyncio
import logging
from typing import Optional, Any, Callable, Coroutine, Dict, Tuple, Union, cast
import datetime

# Import parameter dataclasses for type hinting
from uhf_rfid.protocols.cph.parameters import (
    ExtParams, WorkingParams, TransportParams, AdvanceParams,
    UsbDataParams, DataFlagParams, ModbusParams # Assuming ModbusParams exists
)
# --- Remove direct CPH TLV/Const imports if no longer needed ---
# from uhf_rfid.protocols.cph import tlv # Removed
from uhf_rfid.protocols.cph import constants as cph_const # Still needed for CMD codes

from uhf_rfid.core.dispatcher import Dispatcher, NotificationCallback
from uhf_rfid.core.exceptions import UhfRfidError, TransportError, ConnectionError, TimeoutError, CommandError, \
    ProtocolError
from uhf_rfid.core.status import ConnectionStatus
from uhf_rfid.protocols.base_protocol import BaseProtocol, DeviceInfo, TagReadData
from uhf_rfid.transport.base import BaseTransport
# from uhf_rfid.core.reader_state import ReaderState # Remove incorrect import
# from uhf_rfid.core.schemas.common import TagInfo, FrequencyHop, LockAction, MemoryBank # Remove incorrect import
# import struct # Removed

logger = logging.getLogger(__name__)

# Callback type hint
TagNotifyCallback = Callable[[TagReadData], Coroutine[Any, Any, None]]
StateChangeCallback = Callable[[ConnectionStatus], Coroutine[Any, Any, None]]
ErrorCallback = Callable[[Exception], Coroutine[Any, Any, None]]

class Reader:
    """
    Main class for interacting with a UHF RFID reader using a specified protocol.
    Provides methods for connecting, disconnecting, sending commands,
    and handling tag notifications.
    """

    def __init__(self, transport: BaseTransport, protocol: BaseProtocol, response_timeout: float = 2.0):
        """
        Initializes the Reader.

        Args:
            transport: An instance of a BaseTransport implementation.
            protocol: An instance of a BaseProtocol implementation.
            response_timeout: Default timeout in seconds for waiting command responses.
        """
        if not isinstance(transport, BaseTransport):
            raise TypeError("transport must be an instance of BaseTransport")
        if not isinstance(protocol, BaseProtocol):
             raise TypeError("protocol must be an instance of BaseProtocol")

        self._transport = transport
        self._protocol = protocol # Instance of BaseProtocol
        self._response_timeout = response_timeout

        self._dispatcher: Optional[Dispatcher] = None
        self._state: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self._status_lock = asyncio.Lock()
        self._status_change_callback: Optional[Callable[[ConnectionStatus], Any]] = None
        self._tag_callbacks: List[TagNotifyCallback] = []
        self._state_callbacks: List[StateChangeCallback] = []
        self._error_callbacks: List[ErrorCallback] = []
        self._command_lock = asyncio.Lock()

        logger.debug(f"Reader initialized with transport: {type(transport).__name__} and protocol: {type(protocol).__name__}")

    @property
    def status(self) -> ConnectionStatus:
        """Returns the current connection status."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Returns True if the reader is currently connected."""
        return self._state == ConnectionStatus.CONNECTED

    @property
    def state(self) -> ConnectionStatus:
        """Returns the current state of the reader."""
        return self._state

    async def _update_status(self, new_status: ConnectionStatus):
        """Atomically updates the connection status and calls the callback."""
        async with self._status_lock:
            if self._state != new_status:
                logger.info(f"Reader status changed: {self._state.name} -> {new_status.name}")
                self._state = new_status
                if self._state_callbacks:
                    tasks = [asyncio.create_task(cb(new_status)) for cb in self._state_callbacks]
                    await asyncio.gather(*tasks, return_exceptions=True)
                if self._status_change_callback:
                    try:
                        # Run callback in a separate task to avoid blocking status update
                        asyncio.create_task(self._run_status_callback(new_status))
                    except Exception as e:
                        logger.error(f"Error invoking status change callback: {e}")

    async def _run_status_callback(self, status: ConnectionStatus):
         """Helper to safely run the status callback."""
         if self._status_change_callback:
              if asyncio.iscoroutinefunction(self._status_change_callback):
                   await self._status_change_callback(status)
              else:
                   self._status_change_callback(status)

    def set_status_change_callback(self, callback: Optional[Callable[[ConnectionStatus], Coroutine[Any, Any, None] | None]]):
         """
         Registers a callback function to be notified of connection status changes.
         The callback can be sync or async.
         """
         if callback and not callable(callback):
              raise TypeError("Callback must be callable")
         self._status_change_callback = callback

    async def connect(self) -> None:
        """
        Establishes connection to the reader and initializes the dispatcher.
        """
        if self.is_connected:
            logger.warning("Already connected.")
            return
        if self._state == ReaderState.CONNECTING:
             logger.warning("Connection already in progress.")
             return

        await self._update_status(ReaderState.CONNECTING)
        try:
            # Initialize dispatcher *before* connecting transport might be safer
            # if transport connect starts reading immediately.
            self._dispatcher = Dispatcher(
                transport=self._transport,
                protocol=self._protocol,
                notification_handler=self._handle_notification,
                error_handler=self._report_error
            )
            self._dispatcher.start()
            logger.debug("Dispatcher initialized.")

            await self._transport.connect() # Transport handles its own exceptions (ConnectionError)

            # If connect succeeds, transport should start its read loop which feeds the dispatcher
            await self._update_status(ReaderState.CONNECTED)
            logger.info(f"Reader connected via {type(self._transport).__name__}")

        except ConnectionError as e:
            logger.error(f"Connection failed: {e}")
            await self._update_status(ReaderState.ERROR)
            # Clean up dispatcher if it was created but connection failed
            if self._dispatcher:
                 await self._dispatcher.cleanup()
                 self._dispatcher = None
            raise # Re-raise ConnectionError
        except Exception as e:
            logger.exception(f"Unexpected error during connection: {e}")
            await self._update_status(ReaderState.ERROR)
            if self._dispatcher:
                 await self._dispatcher.cleanup()
                 self._dispatcher = None
            # Wrap unexpected errors in a generic UhfRfidError or re-raise specific ones if known
            raise UhfRfidError(f"Unexpected connection error: {e}") from e

    async def disconnect(self) -> None:
        """
        Disconnects from the reader and cleans up resources.
        """
        if self._state == ReaderState.DISCONNECTED:
            # logger.debug("Already disconnected.") # Can be noisy
            return
        if self._state == ReaderState.DISCONNECTING:
             logger.warning("Disconnection already in progress.")
             return

        await self._update_status(ReaderState.DISCONNECTING)
        try:
            # Stop dispatcher first to prevent processing during/after disconnect
            if self._dispatcher:
                await self._dispatcher.cleanup() # Cancel pending futures
                self._dispatcher = None
                logger.debug("Dispatcher cleaned up.")

            # Disconnect transport (safe to call even if not connected)
            await self._transport.disconnect()
            logger.info("Reader disconnected.")

        except TransportError as e:
            logger.error(f"Error during transport disconnection: {e}")
            # Even if transport fails to disconnect cleanly, we consider the logical state disconnected
        except Exception as e:
            logger.exception(f"Unexpected error during disconnection: {e}")
            # Log but proceed to set status to disconnected
        finally:
            # Always update status, even if errors occurred during cleanup
            await self._update_status(ReaderState.DISCONNECTED)

    async def register_tag_callback(self, callback: NotificationCallback) -> None:
        """
        Registers an asynchronous callback function to receive tag notifications.

        The callback will receive (frame_type, address, frame_code, parsed_params)
        when a tag notification (e.g., frame code 0x80) is received.
        """
        if not self._dispatcher:
            logger.warning("Cannot register callback: Not connected (Dispatcher not initialized).")
            # Or raise an error? raise UhfRfidError("Not connected")
            return
        if not asyncio.iscoroutinefunction(callback):
             raise TypeError("Tag callback must be an async function (defined with 'async def')")
        await self._dispatcher.register_notification_callback(callback)

    async def unregister_tag_callback(self, callback: NotificationCallback) -> None:
        """Unregisters a previously registered tag notification callback."""
        if not self._dispatcher:
            logger.warning("Cannot unregister callback: Not connected.")
            return
        await self._dispatcher.unregister_notification_callback(callback)

    # --- NEW Specific Notification Callback Registration Methods ---

    async def register_tag_notify_callback(self, callback: TagNotifyCallback) -> None:
        """
        Registers an asynchronous callback for tag notifications (online 0x80 and offline 0x81).
        The callback receives (frame_type, address, frame_code, parsed_params).
        """
        if not self._dispatcher:
            raise UhfRfidError("Cannot register callback: Not connected.")
        if not asyncio.iscoroutinefunction(callback):
             raise TypeError("Callback must be an async function (defined with 'async def')")
        # Register for both standard (0x80) and offline (0x81) tag uploads
        try:
             await self._dispatcher.register_notification_callback(cph_const.NOTIF_TAG_UPLOADED, callback)
             await self._dispatcher.register_notification_callback(cph_const.NOTIF_OFFLINE_TAG_UPLOADED, callback)
        except AttributeError:
             logger.error("Missing required constants NOTIF_TAG_UPLOADED or NOTIF_OFFLINE_TAG_UPLOADED")
             raise NotImplementedError("Missing required notification constants")

    async def unregister_tag_notify_callback(self, callback: TagNotifyCallback) -> None:
        """Unregisters a callback from tag notifications (0x80, 0x81)."""
        if not self._dispatcher:
            logger.warning("Cannot unregister callback: Not connected.")
            return
        try:
             await self._dispatcher.unregister_notification_callback(cph_const.CMD_TAG_UPLOAD, callback)
             await self._dispatcher.unregister_notification_callback(cph_const.NOTIF_TAG_UPLOADED, callback)
             await self._dispatcher.unregister_notification_callback(cph_const.NOTIF_OFFLINE_TAG_UPLOADED, callback)
        except AttributeError:
             logger.error("Missing required constants NOTIF_TAG_UPLOADED or NOTIF_OFFLINE_TAG_UPLOADED")
             # Still try to unregister if possible
             pass

    async def register_record_notify_callback(self, callback: NotificationCallback) -> None:
        """
        Registers an asynchronous callback for buffered record notifications (0x82).
        The callback receives (frame_type, address, frame_code, parsed_params).
        """
        if not self._dispatcher:
            raise UhfRfidError("Cannot register callback: Not connected.")
        if not asyncio.iscoroutinefunction(callback):
             raise TypeError("Callback must be an async function (defined with 'async def')")
        try:
             await self._dispatcher.register_notification_callback(cph_const.NOTIF_RECORD_UPLOADED, callback)
        except AttributeError:
             logger.error("Missing required constant NOTIF_RECORD_UPLOADED")
             raise NotImplementedError("Missing required notification constant")

    async def unregister_record_notify_callback(self, callback: NotificationCallback) -> None:
        """Unregisters a callback from record notifications (0x82)."""
        if not self._dispatcher:
            logger.warning("Cannot unregister callback: Not connected.")
            return
        try:
             await self._dispatcher.unregister_notification_callback(cph_const.NOTIF_RECORD_UPLOADED, callback)
        except AttributeError:
             logger.error("Missing required constant NOTIF_RECORD_UPLOADED")
             pass

    async def register_heartbeat_callback(self, callback: NotificationCallback) -> None:
        """
        Registers an asynchronous callback for heartbeat notifications (0x90).
        The callback receives (frame_type, address, frame_code, parsed_params).
        """
        if not self._dispatcher:
            raise UhfRfidError("Cannot register callback: Not connected.")
        if not asyncio.iscoroutinefunction(callback):
             raise TypeError("Callback must be an async function (defined with 'async def')")
        try:
             await self._dispatcher.register_notification_callback(cph_const.NOTIF_HEARTBEAT, callback)
        except AttributeError:
             logger.error("Missing required constant NOTIF_HEARTBEAT")
             raise NotImplementedError("Missing required notification constant")

    async def unregister_heartbeat_callback(self, callback: NotificationCallback) -> None:
        """Unregisters a callback from heartbeat notifications (0x90)."""
        if not self._dispatcher:
            logger.warning("Cannot unregister callback: Not connected.")
            return
        try:
             await self._dispatcher.unregister_notification_callback(cph_const.NOTIF_HEARTBEAT, callback)
        except AttributeError:
             logger.error("Missing required constant NOTIF_HEARTBEAT")
             pass

    async def unregister_callback(self, callback: NotificationCallback) -> None:
         """Unregisters a callback from ALL notification types it might be registered for."""
         if not self._dispatcher:
              logger.warning("Cannot unregister callback: Not connected.")
              return
         await self._dispatcher.unregister_callback_from_all(callback)


    # --- High-level Command Methods ---
    # These methods wrap the dispatcher's send_command_wait_response

    async def _execute_command(self, command_code: int, encode_func: Callable[..., bytes], encode_args: Union[tuple, Dict[str, Any]] = (), decode_func: Optional[Callable[[Dict[Any, Any]], Any]] = None, address: int = 0x0000) -> Any:
        """Internal helper to execute a command and handle response/errors."""
        if not self.is_connected or not self._dispatcher:
            raise ConnectionError("Reader not connected.")

        params_data: bytes
        try:
            # Correctly handle positional or keyword arguments for encode_func
            if isinstance(encode_args, dict):
                params_data = encode_func(**encode_args)
            elif isinstance(encode_args, tuple):
                params_data = encode_func(*encode_args)
            else: # Handle single non-tuple/dict arg or empty case
                params_data = encode_func(encode_args) if encode_args else encode_func()
        except (ProtocolError, ValueError, TypeError) as e:
            logger.error(f"Protocol error encoding command 0x{command_code:02X}: {e}")
            # Wrap encoding error in CommandError with the original message
            raise CommandError(message=f"Failed to encode request for command 0x{command_code:02X}: {e}") from e
        except NotImplementedError:
             logger.error(f"Protocol does not implement encoding for command 0x{command_code:02X}")
             # Wrap NotImplementedError in a more specific CommandError or re-raise?
             # Re-raising seems more appropriate here.
             raise
        except Exception as e:
             logger.exception(f"Unexpected error encoding command 0x{command_code:02X}")
             # Wrap unexpected encoding error in CommandError
             raise CommandError(message=f"Unexpected error encoding request: {e}") from e

        response_params: Dict[Any, Any]
        try:
            response_params = await self._dispatcher.send_command_wait_response(
                command_code=command_code,
                address=address,
                params_data=params_data
            )
        except CommandError as e: # Catch CommandError raised by dispatcher (based on status code)
            logger.error(f"Reader reported error for command 0x{command_code:02X}: Status=0x{e.status_code:02X} ({e.error_message}) Frame={e.frame.hex() if e.frame else 'N/A'}")
            raise # Re-raise the CommandError from the dispatcher
        except TimeoutError as e:
            logger.error(f"Timeout waiting for response to command 0x{command_code:02X}")
            raise # Re-raise TimeoutError
        except UhfRfidError as e:
             # Catch other library-specific errors during send/wait
             logger.error(f"Error during command 0x{command_code:02X}: {e}")
             raise
        except Exception as e:
             # Catch unexpected errors during send/wait
             logger.exception(f"Unexpected error sending/waiting for command 0x{command_code:02X}")
             raise CommandError(message=f"Unexpected error during command send/wait: {e}") from e


        if decode_func:
            try:
                result = decode_func(response_params)
                return result
            except (ProtocolError, ValueError, TypeError, KeyError) as e:
                 logger.error(f"Protocol error decoding response for command 0x{command_code:02X}: {e}")
                 # Include response_params in error? Be careful with sensitive data
                 # Wrap decoding error in CommandError
                 raise CommandError(message=f"Failed to decode response for command 0x{command_code:02X}: {e}") from e
            except NotImplementedError:
                 logger.error(f"Protocol does not implement decoding for command 0x{command_code:02X}")
                 # Re-raise NotImplementedError
            raise
            except Exception as e:
                 logger.exception(f"Unexpected error decoding response for command 0x{command_code:02X}")
                 # Wrap unexpected decoding error in CommandError
                 raise CommandError(message=f"Unexpected error decoding response: {e}") from e
        else:
            # If no decode_func, return None (or raw response_params? Decide API)
            # Returning None is simpler for now.
            return None

    # --- Device Info / Control --- 
    async def get_version(self, address: int = 0x0000) -> DeviceInfo:
        # ... (Correct implementation using _execute_command) ...
        return await self._execute_command(
            command_code=cph_const.CMD_GET_VERSION,
            encode_func=self._protocol.encode_get_version_request,
            decode_func=self._protocol.decode_get_version_response,
            address=address
        )

    async def reboot_reader(self, address: int = 0x0000) -> None:
        # ... (Correct implementation using _execute_command) ...
        await self._execute_command(
            command_code=cph_const.CMD_REBOOT,
            encode_func=self._protocol.encode_reboot_request,
            decode_func=None,
            address=address
        )

    async def set_default_params(self, address: int = 0x0000) -> None:
        """
        Resets the reader's parameters to their factory defaults.
        Use with caution.
        """
        logger.debug(f"Executing set default params (Address: {address})")
        await self._execute_command(
            command_code=cph_const.CMD_SET_DEFAULT_PARAM,
            encode_func=self._protocol.encode_set_default_params_request,
            address=address
        )
        logger.info(f"Set default params command sent successfully (Address: {address})")

    # --- Inventory ---
    async def start_inventory(self, params: Optional[Any] = None, address: int = 0x0000) -> None:
        """Starts continuous inventory mode."""
        # Params can be Gen2Params or None
        logger.debug(f"Executing start inventory (Address: {address}, Params: {params})")
        await self._execute_command(
            command_code=cph_const.CMD_START_INVENTORY,
            encode_func=self._protocol.encode_start_inventory_request,
            encode_args={"params": params} if params else {},
            address=address
        )
        logger.info(f"Start inventory command sent successfully (Address: {address})")

    async def stop_inventory(self, address: int = 0x0000) -> None:
        """Stops continuous inventory mode."""
        logger.debug(f"Executing stop inventory (Address: {address})")
        await self._execute_command(
            command_code=cph_const.CMD_STOP_INVENTORY,
            encode_func=self._protocol.encode_stop_inventory_request,
            address=address
        )
        logger.info(f"Stop inventory command sent successfully (Address: {address})")

    async def inventory_single_burst(self, params: Optional[Any] = None, address: int = 0x0000) -> None:
        """Performs a single inventory burst."""
        # Params can be Gen2Params or None
        logger.debug(f"Executing inventory single burst (Address: {address}, Params: {params})")
        await self._execute_command(
            command_code=cph_const.CMD_ACTIVE_INVENTORY,
            encode_func=self._protocol.encode_inventory_single_burst_request,
            encode_args={"params": params} if params else {},
            address=address
        )
        logger.info(f"Inventory single burst command sent successfully (Address: {address})")

    # --- Single Parameters --- 
    async def set_power(self, power_dbm: int, address: int = 0x0000) -> None:
        """Sets the reader's transmission power."""
        logger.debug(f"Executing set power (Address: {address}, Power: {power_dbm} dBm)")
        await self._execute_command(
            command_code=cph_const.CMD_SET_PARAMETER,
            encode_func=self._protocol.encode_set_power_request,
            encode_args={"power_dbm": power_dbm},
            address=address
        )
        logger.info(f"Set power command sent successfully (Address: {address})")

    async def get_power(self, address: int = 0x0000) -> int:
        """Gets the reader's transmission power."""
        logger.debug(f"Executing get power (Address: {address})")
        # Pass decode_func to _execute_command
        power = await self._execute_command(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            encode_func=self._protocol.encode_get_power_request,
            decode_func=self._protocol.decode_get_power_response,
            address=address
        )
        logger.info(f"Get power successful (Address: {address}): {power} dBm")
        return power

    # ... (set_buzzer, get_buzzer_status, set_filter_time, get_filter_time are correct) ...
    async def set_buzzer(self, enabled: bool, address: int = 0x0000) -> None:
        """Enables or disables the reader's buzzer."""
        logger.debug(f"Executing set buzzer (Address: {address}, Enabled: {enabled})")
        await self._execute_command(
            command_code=cph_const.CMD_SET_PARAMETER,
            encode_func=self._protocol.encode_set_buzzer_request,
            encode_args={"enabled": enabled},
            address=address
        )
        logger.info(f"Set buzzer command sent successfully (Address: {address})")

    async def get_buzzer_status(self, address: int = 0x0000) -> bool:
        """Gets the status of the reader's buzzer."""
        logger.debug(f"Executing get buzzer status (Address: {address})")
        # Pass decode_func to _execute_command
        status = await self._execute_command(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            encode_func=self._protocol.encode_get_buzzer_request,
            decode_func=self._protocol.decode_get_buzzer_response,
            address=address
        )
        logger.info(f"Get buzzer status successful (Address: {address}): {status}")
        return status

    async def set_filter_time(self, filter_time_ms: int, address: int = 0x0000) -> None:
        """Sets the tag filter time (in milliseconds)."""
        logger.debug(f"Executing set filter time (Address: {address}, Time: {filter_time_ms} ms)")
        await self._execute_command(
            command_code=cph_const.CMD_SET_PARAMETER,
            encode_func=self._protocol.encode_set_filter_time_request,
            encode_args={"filter_time_ms": filter_time_ms},
            address=address
        )
        logger.info(f"Set filter time command sent successfully (Address: {address})")

    async def get_filter_time(self, address: int = 0x0000) -> int:
        """Gets the tag filter time (in milliseconds)."""
        logger.debug(f"Executing get filter time (Address: {address})")
        # Pass decode_func to _execute_command
        filter_time = await self._execute_command(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            encode_func=self._protocol.encode_get_filter_time_request,
            decode_func=self._protocol.decode_get_filter_time_response,
            address=address
        )
        logger.info(f"Get filter time successful (Address: {address}): {filter_time} ms")
        return filter_time


    # --- Tag Memory --- 
    async def read_tag_memory(self, bank: int, word_ptr: int, word_count: int, access_password: Optional[bytes] = None, address: int = 0x0000) -> bytes:
        # Already correctly uses _execute_command
        return await self._execute_command(
            command_code=cph_const.CMD_READ_TAG,
            encode_func=self._protocol.encode_read_tag_memory_request,
            encode_args=(bank, word_ptr, word_count, access_password),
            decode_func=self._protocol.decode_read_tag_memory_response,
            address=address
        )

    async def write_tag(
        self,
        mem_bank: int,
        word_addr: int,
        data: bytes,
        access_password: Optional[str] = None,
        address: int = 0x0000,
    ) -> None:
        """Writes data to a tag's memory bank."""
        logger.debug(
            f"Executing write tag (Address: {address}, MemBank: {mem_bank}, "
            f"WordAddr: {word_addr}, Data: {data.hex()}, "
            f"Password: {'*' * len(access_password) if access_password else 'None'}"
            f")"
        )
        await self._execute_command(
            command_code=cph_const.CMD_WRITE_TAG,
            encode_func=self._protocol.encode_write_tag_request,
            encode_args={
                "mem_bank": mem_bank,
                "word_addr": word_addr,
                "data": data,
                "access_password": access_password,
            },
            address=address,
        )
        logger.info(f"Write tag command sent successfully (Address: {address})")

    async def lock_tag(
            self,
        lock_payload: int,  # The lock payload defines which memory banks/permissions are locked
        access_password: str,
        address: int = 0x0000,
    ) -> None:
        """Locks a tag's memory banks based on the specified lock payload."""
        logger.debug(
            f"Executing lock tag (Address: {address}, LockPayload: {lock_payload:#06x}, "
            f"Password: {'*' * len(access_password)}"
            f")"
        )
        await self._execute_command(
            command_code=cph_const.CMD_LOCK_TAG,
            encode_func=self._protocol.encode_lock_tag_request,
            encode_args={
                "lock_payload": lock_payload,
                "access_password": access_password,
            },
            address=address,
        )
        logger.info(f"Lock tag command sent successfully (Address: {address})")

    async def kill_tag(self, kill_password: str) -> None:
        """Sends a command to permanently disable (kill) a tag.

        WARNING: This operation is irreversible and requires the correct
        4-byte Kill Password for the tag. Use with extreme caution.

        Args:
            kill_password: The 4-byte Kill Password as a hexadecimal string (e.g., "FFFFFFFF").

        Raises:
            ValueError: If the kill password format is invalid.
            CommandError: If the reader returns an error status (e.g., wrong password, no tag).
            TransportError: If a transport layer error occurs.
            TimeoutError: If the reader does not respond within the timeout.
            UhfRfidError: For other library-specific errors.
        """
        logger.warning("Attempting to send KILL TAG command - THIS IS IRREVERSIBLE!")
        if not isinstance(kill_password, str) or len(kill_password) != 8:
            raise ValueError("Kill password must be an 8-character hexadecimal string (4 bytes)")
        try:
            pwd_bytes = bytes.fromhex(kill_password)
            if len(pwd_bytes) != 4:
                 raise ValueError("Hex string must represent exactly 4 bytes") # Should be caught by len(kill_password) check
        except ValueError as e:
            raise ValueError(f"Invalid hexadecimal string for kill password: {e}") from e

        await self._execute_command(
            command_code=cph_const.CMD_LOCK_TAG, # Kill uses the Lock command code
            encode_func=self._protocol.encode_kill_tag_request,
            encode_args={"kill_password": pwd_bytes},
            command_name="Kill Tag"
        )
        # No data is expected in the response for a successful kill command
        logger.info("Kill Tag command sent successfully.")

    # --- RTC --- 
    async def get_rtc_time(self, address: int = 0x0000) -> datetime.datetime:
        """ Gets the reader's Real-Time Clock value. """
        # REMOVE CPH specific parsing, rely on protocol decode
        logger.info(f"Querying RTC time from address 0x{address:04X}...")
        # Determine encode func (might be missing in base, provide default)
        encode_func = getattr(self._protocol, 'encode_get_rtc_request', lambda: b'')
        
        return await self._execute_command(
            command_code=cph_const.CMD_QUERY_RTC_TIME,
            encode_func=encode_func,
            decode_func=self._protocol.decode_get_rtc_response,
            address=address
        )

    async def set_rtc_time(self, time_to_set: datetime.datetime, address: int = 0x0000) -> None:
        # Already correctly uses _execute_command
        await self._execute_command(
            command_code=cph_const.CMD_SET_RTC_TIME,
            encode_func=self._protocol.encode_set_rtc_request,
            encode_args=(time_to_set,),
            decode_func=None,
            address=address
        )

    # --- Complex Parameter Sets --- 
    # ... (get/set methods for ExtParams, WorkingParams, etc. are correct) ...
    async def get_ext_params(self, address: int = 0x0000) -> ExtParams:
        encode_func = getattr(self._protocol, 'encode_get_ext_params_request', lambda: b'')
        return await self._execute_command(
            command_code=cph_const.CMD_QUERY_EXT_PARAM,
            encode_func=encode_func,
            decode_func=self._protocol.decode_get_ext_params_response,
            address=address
        )

    async def set_ext_params(self, params: ExtParams, address: int = 0x0000) -> None:
        await self._execute_command(
            command_code=cph_const.CMD_SET_EXT_PARAM,
            encode_func=self._protocol.encode_set_ext_params_request,
            encode_args=(params,),
            decode_func=None,
            address=address
        )

    async def get_working_params(self, address: int = 0x0000) -> WorkingParams:
        encode_func = getattr(self._protocol, 'encode_get_working_params_request', lambda: b'')
        return await self._execute_command(
            command_code=cph_const.CMD_QUERY_WORKING_PARAM,
            encode_func=encode_func,
            decode_func=self._protocol.decode_get_working_params_response,
            address=address
        )

    async def set_working_params(self, params: WorkingParams, address: int = 0x0000) -> None:
        await self._execute_command(
            command_code=cph_const.CMD_SET_WORKING_PARAM,
            encode_func=self._protocol.encode_set_working_params_request,
            encode_args=(params,),
            decode_func=None,
            address=address
        )

    async def get_transport_params(self, address: int = 0x0000) -> TransportParams:
        encode_func = getattr(self._protocol, 'encode_get_transport_params_request', lambda: b'')
        return await self._execute_command(
            command_code=cph_const.CMD_QUERY_TRANSPORT_PARAM,
            encode_func=encode_func,
            decode_func=self._protocol.decode_get_transport_params_response,
            address=address
        )

    async def set_transport_params(self, params: TransportParams, address: int = 0x0000) -> None:
        await self._execute_command(
            command_code=cph_const.CMD_SET_TRANSPORT_PARAM,
            encode_func=self._protocol.encode_set_transport_params_request,
            encode_args=(params,),
            decode_func=None,
            address=address
        )

    async def get_advance_params(self, address: int = 0x0000) -> AdvanceParams:
        encode_func = getattr(self._protocol, 'encode_get_advance_params_request', lambda: b'')
        return await self._execute_command(
            command_code=cph_const.CMD_QUERY_ADVANCE_PARAM,
            encode_func=encode_func,
            decode_func=self._protocol.decode_get_advance_params_response,
            address=address
        )

    async def set_advance_params(self, params: AdvanceParams, address: int = 0x0000) -> None:
        await self._execute_command(
            command_code=cph_const.CMD_SET_ADVANCE_PARAM,
            encode_func=self._protocol.encode_set_advance_params_request,
            encode_args=(params,),
            decode_func=None,
            address=address
        )

    async def get_usb_data_params(self, address: int = 0x0000) -> UsbDataParams:
         encode_func = getattr(self._protocol, 'encode_get_usb_data_params_request', lambda: b'')
         return await self._execute_command(
             command_code=cph_const.CMD_QUERY_USB_DATA,
             encode_func=encode_func,
             decode_func=self._protocol.decode_get_usb_data_params_response,
             address=address
         )

    async def set_usb_data_params(self, params: UsbDataParams, address: int = 0x0000) -> None:
         await self._execute_command(
             command_code=cph_const.CMD_SET_USB_DATA,
             encode_func=self._protocol.encode_set_usb_data_params_request,
             encode_args=(params,),
             decode_func=None,
             address=address
         )

    async def get_data_flag_params(self, address: int = 0x0000) -> DataFlagParams:
         encode_func = getattr(self._protocol, 'encode_get_data_flag_params_request', lambda: b'')
         return await self._execute_command(
             command_code=cph_const.CMD_QUERY_DATA_FLAG,
             encode_func=encode_func,
             decode_func=self._protocol.decode_get_data_flag_params_response,
             address=address
         )

    async def set_data_flag_params(self, params: DataFlagParams, address: int = 0x0000) -> None:
         await self._execute_command(
             command_code=cph_const.CMD_SET_DATA_FLAG,
             encode_func=self._protocol.encode_set_data_flag_params_request,
             encode_args=(params,),
             decode_func=None,
             address=address
         )

    async def get_modbus_params(self, address: int = 0x0000) -> ModbusParams:
         encode_func = getattr(self._protocol, 'encode_get_modbus_params_request', lambda: b'')
         return await self._execute_command(
             command_code=cph_const.CMD_QUERY_MODBUS_PARAM,
             encode_func=encode_func,
             decode_func=self._protocol.decode_get_modbus_params_response,
             address=address
         )

    async def set_modbus_params(self, params: ModbusParams, address: int = 0x0000) -> None:
         await self._execute_command(
             command_code=cph_const.CMD_SET_MODBUS_PARAM,
             encode_func=self._protocol.encode_set_modbus_params_request,
             encode_args=(params,),
             decode_func=None,
             address=address
         )

    # --- Misc Commands --- 
    # ... (relay_operation, play_audio are correct) ...
    async def relay_operation(self, relay_state: int, address: int = 0x0000) -> None:
        await self._execute_command(
            command_code=cph_const.CMD_RELAY_OP,
            encode_func=self._protocol.encode_relay_op_request,
            encode_args=(relay_state,),
            decode_func=None,
            address=address
        )

    async def play_audio(self, audio_data: Union[str, bytes], encoding: str = 'utf-8', address: int = 0x0000) -> None:
        if isinstance(audio_data, str):
             payload = audio_data.encode(encoding)
        else:
             payload = audio_data
        await self._execute_command(
            command_code=cph_const.CMD_AUDIO_PLAY,
            encode_func=self._protocol.encode_audio_play_request,
            encode_args=(payload,),
            decode_func=None,
            address=address
        )

    # --- Tag Operations ---

    async def read_tag(
        self,
        mem_bank: int,
        word_addr: int,
        word_count: int,
        access_password: Optional[str] = None,
        address: int = 0x0000,
    ) -> bytes:
        """Reads data from a tag's memory bank."""
        logger.debug(
            f"Executing read tag (Address: {address}, MemBank: {mem_bank}, "
            f"WordAddr: {word_addr}, WordCount: {word_count}, "
            f"Password: {'*' * len(access_password) if access_password else 'None'}"
            f")"
        )
        # Pass decode_func to _execute_command
        tag_data = await self._execute_command(
            command_code=cph_const.CMD_READ_TAG,
            encode_func=self._protocol.encode_read_tag_request,
            encode_args={
                "mem_bank": mem_bank,
                "word_addr": word_addr,
                "word_count": word_count,
                "access_password": access_password,
            },
            decode_func=self._protocol.decode_read_tag_response,
            address=address,
        )
        logger.info(f"Read tag successful (Address: {address}): {tag_data.hex()}")
        return tag_data

    # --- Context Manager --- 
    async def __aenter__(self):
        # ... (no changes) ...
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # ... (no changes) ...
        await self.disconnect()