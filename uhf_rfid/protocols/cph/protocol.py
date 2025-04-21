# uhf_rfid/protocols/cph/protocol.py

import logging
import datetime
from typing import Dict, Any, Optional, Callable, Type, TypeVar, Union, Tuple

# Absolute imports
from uhf_rfid.protocols.base_protocol import (
    BaseProtocol, DeviceInfo, TagReadData,
    PARAM_TYPE_POWER, PARAM_TYPE_BUZZER, PARAM_TYPE_TAG_FILTER_TIME
)
from uhf_rfid.protocols import framing
from uhf_rfid.core.exceptions import (
    ProtocolError, CommandError, TLVParseError,
    FrameParseError, ChecksumError
)
from uhf_rfid.protocols.cph import tlv
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph import commands_device
from uhf_rfid.protocols.cph import commands_params
from uhf_rfid.protocols.cph import commands_tags
from uhf_rfid.protocols.cph import commands_misc
from uhf_rfid.protocols.cph.parameters import (
    WorkingParams, ExtParams, TransportParams, AdvanceParams,
    ModbusParams, UsbDataParams, DataFlagParams
)

logger = logging.getLogger(__name__)

class CPHProtocol(BaseProtocol):
    """
    Implements the CPH RFID Communication Protocol Version 4.0.1.
    Handles encoding commands and decoding responses/notifications by delegating
    to command-specific functions.
    """
    #FRAME_HEADER = cph_const.FRAME_HEADER

    # encode_command remains the same
    def encode_command(self, command_code: int, address: int = 0x0000, params_data: bytes = b'') -> bytes:
        # ... (no changes needed here) ...
        return framing.build_frame(
            frame_type=cph_const.FRAME_TYPE_COMMAND,
            address=address,
            frame_code=command_code,
            parameters=params_data
        )

    # decode_frame method adjusted to handle specific exceptions
    def decode_frame(self, frame_bytes: bytes) -> Tuple[int, int, int, bytes]:
        # ... (print statement) ...
        if not frame_bytes.startswith(cph_const.FRAME_HEADER):
            raise FrameParseError(
                f"Frame does not start with header '{cph_const.FRAME_HEADER.decode()}'",
                frame_part=frame_bytes[:cph_const.HEADER_LENGTH]
            )
        try:
            frame_type, address, frame_code, param_len_expected, parameters, _, _ = framing.parse_frame_header(frame_bytes)
            if len(parameters) != param_len_expected:
                logger.error(f"Parameter length mismatch after frame decode: Expected {param_len_expected}, Got {len(parameters)}")
                raise FrameParseError(f"Internal decode error: parameter length mismatch (expected {param_len_expected}, got {len(parameters)})", frame_part=frame_bytes)
            logger.debug(f"Decoded Frame: Type=0x{frame_type:02X}, Addr=0x{address:04X}, Code=0x{frame_code:02X}, ParamsLen={len(parameters)}")
            return frame_type, address, frame_code, parameters
        except (FrameParseError, ChecksumError) as e: # Now these exceptions are defined
            logger.error(f"Error during frame header parsing: {e}")
            raise e # Re-raise the specific error
        except Exception as e:
             logger.exception(f"Unexpected error decoding validated frame: {e}")
             raise ProtocolError(f"Unexpected error decoding frame: {e}") from e

    # parse_parameters adjusted to use imported tlv module
    def parse_parameters(self, command_code: int, frame_type: int, params_bytes: bytes) -> Dict[Any, Any]:
        """ Parses CPH parameter bytes into a dictionary of TLVs. """
        if not params_bytes:
            return {}
        logger.debug(f"Parsing parameters for Cmd/Notif=0x{command_code:02X}, Type=0x{frame_type:02X}: {params_bytes.hex(' ')}")
        try:
            parsed_tlvs = tlv.parse_tlv_sequence(params_bytes) # Use imported tlv
            logger.debug(f"Parsed TLVs: {parsed_tlvs}")
            return parsed_tlvs
        except TLVParseError as e:
            logger.error(f"TLV parsing failed for Cmd/Notif=0x{command_code:02X}, Type=0x{frame_type:02X}: {e}")
            raise ProtocolError(f"TLV parsing error: {e}") from e
        except Exception as e:
             logger.exception(f"Unexpected error parsing parameters for Cmd/Notif=0x{command_code:02X}, Type=0x{frame_type:02X}: {e}")
             raise ProtocolError(f"Unexpected error during CPH parameter parsing: {e}") from e

    # calculate_checksum remains the same
    @staticmethod
    def calculate_checksum(data: bytes) -> int:
        return framing.calculate_checksum(data)

    # --- High-level Command Encoding/Decoding (Delegated) ---

    # --- Device Control ---
    def encode_reboot_request(self) -> bytes:
        return commands_device.encode_reboot_request()

    def encode_set_default_params_request(self) -> bytes:
        # CMD_SET_DEFAULT_PARAM (0x12) - CPH spec shows no parameters
        return b''

    # --- Device Info ---
    def encode_get_version_request(self) -> bytes:
        return commands_device.encode_get_version_request()

    def decode_get_version_response(self, parsed_params: Dict[Any, Any]) -> DeviceInfo:
        return commands_device.decode_get_version_response(parsed_params)

    # --- Single Parameter Commands ---
    def encode_set_power_request(self, power_dbm: int) -> bytes:
        # Uses CMD_SET_PARAMETER (0x48) with specific TLV
        return commands_params.encode_set_single_param_request(cph_const.PARAM_TYPE_POWER, power_dbm)

    def encode_set_buzzer_request(self, enabled: bool) -> bytes:
        # Uses CMD_SET_PARAMETER (0x48) with specific TLV
        return commands_params.encode_set_single_param_request(cph_const.PARAM_TYPE_BUZZER, enabled)

    def encode_set_filter_time_request(self, seconds: int) -> bytes:
        # Uses CMD_SET_PARAMETER (0x48) with specific TLV
        return commands_params.encode_set_single_param_request(cph_const.PARAM_TYPE_TAG_FILTER_TIME, seconds)

    def encode_query_parameter_request(self, param_type: int) -> bytes:
        # Uses CMD_QUERY_PARAMETER (0x49) with specific TLV
        return commands_params.encode_query_single_param_request(param_type)

    # Decode methods for single parameters extract from the generic response TLV
    def decode_get_power_response(self, parsed_params: Dict[Any, Any]) -> int:
        value_bytes = commands_params.decode_query_single_param_response(cph_const.PARAM_TYPE_POWER, parsed_params)
        if len(value_bytes) == 1:
            return value_bytes[0]
        raise ProtocolError(f"Invalid power value length in response: {len(value_bytes)} bytes", frame_part=value_bytes)

    def decode_get_buzzer_response(self, parsed_params: Dict[Any, Any]) -> bool:
        value_bytes = commands_params.decode_query_single_param_response(cph_const.PARAM_TYPE_BUZZER, parsed_params)
        if len(value_bytes) == 1:
            return value_bytes[0] != 0
        raise ProtocolError(f"Invalid buzzer value length in response: {len(value_bytes)} bytes", frame_part=value_bytes)

    def decode_get_filter_time_response(self, parsed_params: Dict[Any, Any]) -> int:
        value_bytes = commands_params.decode_query_single_param_response(cph_const.PARAM_TYPE_TAG_FILTER_TIME, parsed_params)
        if len(value_bytes) == 1:
            return value_bytes[0]
        raise ProtocolError(f"Invalid filter time value length in response: {len(value_bytes)} bytes", frame_part=value_bytes)

    def decode_query_parameter_response(self, param_type: int, parsed_params: Dict[Any, Any]) -> bytes:
         # Base method already returns raw bytes, specific decodes handle interpretation
         return commands_params.decode_query_single_param_response(param_type, parsed_params)

    # --- Complex Parameter Sets ---
    def encode_set_ext_params_request(self, params: ExtParams) -> bytes:
        return commands_params.encode_set_ext_params_request(params)

    def decode_get_ext_params_response(self, parsed_params: Dict[Any, Any]) -> ExtParams:
        return commands_params.decode_get_ext_params_response(parsed_params)

    def encode_set_working_params_request(self, params: WorkingParams) -> bytes:
        return commands_params.encode_set_working_params_request(params)

    def decode_get_working_params_response(self, parsed_params: Dict[Any, Any]) -> WorkingParams:
        return commands_params.decode_get_working_params_response(parsed_params)

    def encode_set_transport_params_request(self, params: TransportParams) -> bytes:
        return commands_params.encode_set_transport_params_request(params)

    def decode_get_transport_params_response(self, parsed_params: Dict[Any, Any]) -> TransportParams:
        return commands_params.decode_get_transport_params_response(parsed_params)

    def encode_set_advance_params_request(self, params: AdvanceParams) -> bytes:
        return commands_params.encode_set_advance_params_request(params)

    def decode_get_advance_params_response(self, parsed_params: Dict[Any, Any]) -> AdvanceParams:
        return commands_params.decode_get_advance_params_response(parsed_params)

    def encode_set_usb_data_params_request(self, params: UsbDataParams) -> bytes:
        return commands_misc.encode_set_usb_data_params_request(params)

    def decode_get_usb_data_params_response(self, parsed_params: Dict[Any, Any]) -> UsbDataParams:
        return commands_misc.decode_get_usb_data_params_response(parsed_params)

    def encode_set_data_flag_params_request(self, params: DataFlagParams) -> bytes:
        return commands_misc.encode_set_data_flag_params_request(params)

    def decode_get_data_flag_params_response(self, parsed_params: Dict[Any, Any]) -> DataFlagParams:
        return commands_misc.decode_get_data_flag_params_response(parsed_params)

    def encode_set_modbus_params_request(self, params: ModbusParams) -> bytes:
        return commands_misc.encode_set_modbus_params_request(params)

    def decode_get_modbus_params_response(self, parsed_params: Dict[Any, Any]) -> ModbusParams:
        return commands_misc.decode_get_modbus_params_response(parsed_params)

    # --- RTC ---
    def encode_set_rtc_request(self, time_to_set: datetime.datetime) -> bytes:
        return commands_device.encode_set_rtc_request(time_to_set)

    def decode_get_rtc_response(self, parsed_params: Dict[Any, Any]) -> datetime.datetime:
        return commands_device.decode_get_rtc_response(parsed_params)

    # --- Tag Inventory ---
    def encode_start_inventory_request(self, params: Optional[Any] = None) -> bytes:
        return commands_tags.encode_start_inventory_request(params)

    def encode_active_inventory_request(self, params: Optional[Any] = None) -> bytes:
        return commands_tags.encode_active_inventory_request(params)

    def encode_stop_inventory_request(self) -> bytes:
        return commands_tags.encode_stop_inventory_request()

    # --- Tag Memory ---
    def encode_read_tag_memory_request(self, bank: int, word_ptr: int, word_count: int, password: Optional[bytes] = None) -> bytes:
        return commands_tags.encode_read_tag_memory_request(bank, word_ptr, word_count, password)

    def decode_read_tag_memory_response(self, parsed_params: Dict[Any, Any]) -> bytes:
        return commands_tags.decode_read_tag_memory_response(parsed_params)

    def encode_write_tag_memory_request(self, bank: int, word_ptr: int, data: bytes, password: Optional[bytes] = None) -> bytes:
        return commands_tags.encode_write_tag_memory_request(bank, word_ptr, data, password)

    # --- Tag Locking ---
    def encode_lock_tag_request(self, lock_type: int, password: Optional[bytes] = None) -> bytes:
        return commands_tags.encode_lock_tag_request(lock_type, password)

    # --- Tag Kill ---
    def encode_kill_tag_request(self, kill_password: bytes) -> bytes:
        return commands_tags.encode_kill_tag_request(kill_password)

    # --- Relay / Audio ---
    def encode_relay_op_request(self, relay_state: int) -> bytes:
        return commands_misc.encode_relay_op_request(relay_state)

    def encode_audio_play_request(self, audio_data: bytes) -> bytes:
        return commands_misc.encode_audio_play_request(audio_data)

    # --- Notifications ---
    def parse_notification_params(self, frame_code: int, params_bytes: bytes) -> Union[TagReadData, Any]:
        """ Parses notification parameters based on the frame code. """
        logger.debug(f"Parsing Notification Code=0x{frame_code:02X}, Params: {params_bytes.hex(' ')}")
        if frame_code in [cph_const.NOTIF_TAG_UPLOADED, cph_const.NOTIF_OFFLINE_TAG_UPLOADED]:
            try:
                return commands_tags.parse_tag_notification_params(params_bytes)
            except ProtocolError as e: # Catch specific parsing errors for tag data
                 logger.error(f"Failed to parse tag notification (0x{frame_code:02X}): {e}")
                 # Return a basic dict indicating error, or re-raise?
                 # Returning a dict might prevent dispatcher from crashing if one notif is bad.
                 return {"error": "Failed to parse tag data", "details": str(e), "raw_params": params_bytes}

        # Add parsing for other known notifications (Record, Heartbeat) by delegating
        # elif frame_code == cph_const.NOTIF_RECORD_UPLOADED:
        #     # return commands_misc.parse_record_notification_params(params_bytes)
        # elif frame_code == cph_const.NOTIF_HEARTBEAT:
        #     # return commands_misc.parse_heartbeat_notification_params(params_bytes)

        else:
            # Default handling for unknown notifications: try to parse as generic TLV
            logger.warning(f"Parsing unknown notification frame code 0x{frame_code:02X} as generic TLV")
            try:
                # Use the base parse_parameters which just does TLV parsing
                return self.parse_parameters(command_code=frame_code, frame_type=cph_const.FRAME_TYPE_NOTIFICATION, params_bytes=params_bytes)
            except ProtocolError as e:
                 logger.error(f"Failed to parse unknown notification 0x{frame_code:02X} as TLV: {e}")
                 return {"error": "Failed to parse unknown notification", "details": str(e), "raw_params": params_bytes}

    def get_status_from_response(self, parsed_params: Dict[Any, Any]) -> int:
        """ Extracts status code from TAG_STATUS TLV in a CPH response. """
        status_bytes = parsed_params.get(cph_const.TAG_STATUS)
        if status_bytes is None:
            # CPH spec v4.0.1 implies status is always present in responses.
            logger.error(f"Status TLV (0x07) missing in CPH response. Params: {parsed_params}")
            raise ProtocolError("Status TLV (0x07) missing in response", frame_part=parsed_params)

        if isinstance(status_bytes, bytes) and len(status_bytes) == 1:
            status_code = status_bytes[0]
            logger.debug(f"Extracted status code: 0x{status_code:02X}")
            return status_code
        elif isinstance(status_bytes, int): # If tlv parser already converted single byte int
             logger.debug(f"Extracted status code (already int): 0x{status_bytes:02X}")
             return status_bytes
        else:
             logger.error(f"Invalid status TLV format: Expected 1 byte, got {status_bytes!r} (type {type(status_bytes)})")
             raise ProtocolError(f"Invalid status TLV format: Expected 1 byte, got {status_bytes!r}", frame_part=status_bytes)

    def get_error_message(self, status_code: int) -> str:
        """ Returns CPH error message for a status code. """
        return cph_const.CPH_STATUS_MESSAGES.get(status_code, f"Unknown CPH Status Code: 0x{status_code:02X}")