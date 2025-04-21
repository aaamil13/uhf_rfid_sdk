# uhf_rfid/protocols/base_protocol.py
import abc
import datetime
from typing import Any, Coroutine, Dict, Tuple, Optional, Union, List

# Define common data structures (може да се изнесат в uhf_rfid/common/ R later)
from dataclasses import dataclass

# Import parameter dataclasses - assuming they exist here
# If not, adjust the import path
from uhf_rfid.protocols.cph.parameters import (
    ExtParams,
    WorkingParams,
    TransportParams,
    AdvanceParams,
    UsbDataParams,
    DataFlagParams,
    ModbusParams # Assuming ModbusParams exists
)

# Common parameter types (could be enums)
PARAM_TYPE_POWER = 0x01
PARAM_TYPE_BUZZER = 0x02
PARAM_TYPE_TAG_FILTER_TIME = 0x03
PARAM_TYPE_MODEM = 0x04

# Memory banks (could be enums)
MEM_BANK_RESERVED = 0x00
MEM_BANK_EPC = 0x01
MEM_BANK_TID = 0x02
MEM_BANK_USER = 0x03

# Relay states (could be enums)
RELAY_OFF = 0x00
RELAY_ON = 0x01
RELAY_PULSE = 0x02

@dataclass
class DeviceInfo:
    # Примерна структура, може да се разшири
    software_version: str = "N/A"
    hardware_version: str = "N/A"
    manufacturer: str = "N/A"
    model: str = "N/A"
    serial_number: str = "N/A"

@dataclass
class TagReadData:
     # Примерна структура
     epc: str
     tid: Optional[str] = None
     user_data: Optional[bytes] = None
     rssi: Optional[int] = None
     antenna: Optional[int] = None
     timestamp: Optional[datetime.datetime] = None


class BaseProtocol(abc.ABC):
    """Abstract Base Class for RFID reader communication protocols."""

    # --- Low-level methods required by Dispatcher/Reader ---

    def encode_command(self, command_code: int, address: int = 0x0000, params_data: bytes = b'') -> bytes:
        """
        Encodes a command with its parameters into a full frame ready for sending.
        (This might be primarily used by Dispatcher or for raw command sending).
        """
        raise NotImplementedError

    def parse_frame(self, data: bytes) -> Tuple[Optional[bytes], bytes]:
        """
        Attempts to parse a complete frame from the beginning of the buffer.

        Returns:
            A tuple: (parsed_frame, remaining_buffer).
            parsed_frame is None if no complete frame is found.
        """
        raise NotImplementedError

    def decode_frame(self, frame: bytes) -> Tuple[int, int, int, bytes]:
        """
        Decodes a complete, validated frame into its components.

        Returns:
            Tuple: (frame_type, address, frame_code, parameters_bytes)
        Raises:
            ProtocolError: If the frame structure is invalid (after initial parsing).
        """
        raise NotImplementedError

    def parse_parameters(self, command_code: int, frame_type: int, params_bytes: bytes) -> Dict[Any, Any]:
        """
        Parses the parameter bytes of a *response* or *notification* frame
        into a more usable format (e.g., a dictionary).
        The exact structure depends on the protocol (e.g., TLV for CPH).
        """
        raise NotImplementedError

    def get_status_from_response(self, parsed_params: Dict[Any, Any]) -> int:
        """
        Extracts the status code from parsed response parameters.
        Must return a standard success code (e.g., 0) on success.
        """
        raise NotImplementedError

    def get_error_message(self, status_code: int) -> str:
        """
        Returns a descriptive error message for a given protocol status code.
        """
        raise NotImplementedError

    # --- High-level Command Encoding/Decoding --- 
    # Reader ще извиква тези методи, за да подготви params_data 
    # или да интерпретира отговора.

    # --- Device Info ---
    def encode_get_version_request(self) -> bytes:
        """ Returns the raw parameter bytes needed for the get_version command. """
        raise NotImplementedError # Usually empty: return b''

    def decode_get_version_response(self, parsed_params: Dict[Any, Any]) -> DeviceInfo:
        """ Decodes parsed response parameters into a standard DeviceInfo object. """
        raise NotImplementedError

    # --- Power ---
    def encode_set_power_request(self, power_dbm: int) -> bytes:
        """ Encodes the power setting request parameters. """
        raise NotImplementedError

    def decode_get_power_response(self, parsed_params: Dict[Any, Any]) -> int:
        """ Decodes the power level (dBm) from parsed response parameters. """
        raise NotImplementedError

    # --- RTC ---
    def encode_set_rtc_request(self, time_to_set: datetime.datetime) -> bytes:
        """ Encodes the RTC setting request parameters. """
        raise NotImplementedError

    def decode_get_rtc_response(self, parsed_params: Dict[Any, Any]) -> datetime.datetime:
        """ Decodes the datetime object from parsed response parameters. """
        raise NotImplementedError

    # --- Tag Memory ---
    def encode_read_tag_memory_request(self, bank: int, word_ptr: int, word_count: int, password: bytes) -> bytes:
        """ Encodes the read tag memory request parameters. """
        raise NotImplementedError

    def decode_read_tag_memory_response(self, parsed_params: Dict[Any, Any]) -> bytes:
        """ Decodes the read data from parsed response parameters. """
        raise NotImplementedError

    def encode_write_tag_memory_request(self, bank: int, word_ptr: int, data: bytes, password: bytes) -> bytes:
        """ Encodes the write tag memory request parameters. """
        raise NotImplementedError

    # --- Notifications ---
    def parse_notification_params(self, frame_code: int, params_bytes: bytes) -> Union[TagReadData, Any]:
         """
         Parses notification parameter bytes into a structured object (e.g., TagReadData).
         Returns specific object type based on frame_code or generic dict/bytes if unknown.
         """
         raise NotImplementedError

    # --- Device Control --- 
    def encode_reboot_request(self) -> bytes:
        """ Encodes parameters for the reboot command (usually empty). """
        raise NotImplementedError # return b''

    def encode_set_default_params_request(self) -> bytes:
        """ Encodes parameters for setting default parameters (usually empty). """
        raise NotImplementedError # return b''

    # --- Single Parameter Commands ---
    def encode_set_buzzer_request(self, enabled: bool) -> bytes:
        """ Encodes parameters to enable/disable the buzzer. """
        raise NotImplementedError

    def encode_set_filter_time_request(self, seconds: int) -> bytes:
        """ Encodes parameters to set the tag filter time. """
        raise NotImplementedError

    def encode_query_parameter_request(self, param_type: int) -> bytes:
         """ Encodes parameters to query a single parameter type. """
         raise NotImplementedError

    def decode_get_buzzer_response(self, parsed_params: Dict[Any, Any]) -> bool:
        """ Decodes the buzzer status from parsed response parameters. """
        raise NotImplementedError

    def decode_get_filter_time_response(self, parsed_params: Dict[Any, Any]) -> int:
        """ Decodes the tag filter time (seconds) from parsed response parameters. """
        raise NotImplementedError
    
    def decode_query_parameter_response(self, param_type: int, parsed_params: Dict[Any, Any]) -> bytes:
         """ Decodes the raw value of a queried single parameter. """
         raise NotImplementedError

    # --- Complex Parameter Sets --- 
    def encode_set_ext_params_request(self, params: ExtParams) -> bytes:
        """ Encodes the ExtParams object into request parameters. """
        raise NotImplementedError

    def decode_get_ext_params_response(self, parsed_params: Dict[Any, Any]) -> ExtParams:
        """ Decodes response parameters into an ExtParams object. """
        raise NotImplementedError

    def encode_set_working_params_request(self, params: WorkingParams) -> bytes:
        """ Encodes the WorkingParams object into request parameters. """
        raise NotImplementedError

    def decode_get_working_params_response(self, parsed_params: Dict[Any, Any]) -> WorkingParams:
        """ Decodes response parameters into a WorkingParams object. """
        raise NotImplementedError

    def encode_set_transport_params_request(self, params: TransportParams) -> bytes:
        """ Encodes the TransportParams object into request parameters. """
        raise NotImplementedError

    def decode_get_transport_params_response(self, parsed_params: Dict[Any, Any]) -> TransportParams:
        """ Decodes response parameters into a TransportParams object. """
        raise NotImplementedError

    def encode_set_advance_params_request(self, params: AdvanceParams) -> bytes:
        """ Encodes the AdvanceParams object into request parameters. """
        raise NotImplementedError

    def decode_get_advance_params_response(self, parsed_params: Dict[Any, Any]) -> AdvanceParams:
        """ Decodes response parameters into an AdvanceParams object. """
        raise NotImplementedError

    def encode_set_usb_data_params_request(self, params: UsbDataParams) -> bytes:
        """ Encodes the UsbDataParams object into request parameters. """
        raise NotImplementedError

    def decode_get_usb_data_params_response(self, parsed_params: Dict[Any, Any]) -> UsbDataParams:
        """ Decodes response parameters into a UsbDataParams object. """
        raise NotImplementedError

    def encode_set_data_flag_params_request(self, params: DataFlagParams) -> bytes:
        """ Encodes the DataFlagParams object into request parameters. """
        raise NotImplementedError

    def decode_get_data_flag_params_response(self, parsed_params: Dict[Any, Any]) -> DataFlagParams:
        """ Decodes response parameters into a DataFlagParams object. """
        raise NotImplementedError

    def encode_set_modbus_params_request(self, params: ModbusParams) -> bytes:
        """ Encodes the ModbusParams object into request parameters. """
        raise NotImplementedError

    def decode_get_modbus_params_response(self, parsed_params: Dict[Any, Any]) -> ModbusParams:
        """ Decodes response parameters into a ModbusParams object. """
        raise NotImplementedError

    # --- Tag Inventory --- 
    def encode_start_inventory_request(self, params: Optional[Any] = None) -> bytes:
        """ Encodes parameters to start continuous inventory. `params` are protocol specific. """
        raise NotImplementedError

    def encode_active_inventory_request(self, params: Optional[Any] = None) -> bytes:
        """ Encodes parameters to start a single inventory burst. `params` are protocol specific. """
        raise NotImplementedError

    def encode_stop_inventory_request(self) -> bytes:
        """ Encodes parameters to stop inventory (usually empty). """
        raise NotImplementedError # return b''

    # --- Tag Locking --- 
    def encode_lock_tag_request(self, lock_type: int, password: Optional[bytes] = None) -> bytes:
        """ Encodes parameters to lock tag memory. `lock_type` is protocol specific. """
        raise NotImplementedError

    # --- Relay / Audio --- 
    def encode_relay_op_request(self, relay_state: int) -> bytes:
        """ Encodes parameters to control the relay. `relay_state` is protocol specific. """
        raise NotImplementedError

    def encode_audio_play_request(self, audio_data: bytes) -> bytes:
        """ Encodes parameters to play audio (e.g., text or sound index). """
        raise NotImplementedError

    # ... добави още абстрактни методи за други команди ...
    # (set_buzzer, get_buzzer, set_filter_time, get_filter_time, lock_tag, etc.)
    # ... както и съответните encode/decode методи за тях.
