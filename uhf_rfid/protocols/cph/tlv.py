# uhf_rfid/protocols/cph/tlv.py

import logging
import struct
from typing import Dict, Any, Tuple, Optional

from uhf_rfid.core.exceptions import TLVParseError
# Import constants
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph.parameters import ExtParams, WorkingParams, TransportParams, AdvanceParams


logger = logging.getLogger(__name__)

# --- Parsing Functions ---

def parse_tlv(data: bytes) -> Tuple[int, int, bytes, int]:
    """
    Parses the first TLV structure found in the data.
    Assumes the Length field is 1 byte.
    """
    min_tlv_header_len = 2 # Tag + Length
    if len(data) < min_tlv_header_len:
        raise TLVParseError(f"Insufficient data for TLV header (need {min_tlv_header_len}, got {len(data)})", tlv_data=data)

    tag = data[0]
    length = data[1] # Assuming 1-byte length field
    value_start = min_tlv_header_len
    value_end = value_start + length
    consumed_length = value_end

    if len(data) < consumed_length:
        raise TLVParseError(
            f"Declared TLV length ({length}) exceeds available data ({len(data) - value_start} bytes after header)",
            tlv_data=data
        )

    value = data[value_start:value_end]
    return tag, length, value, consumed_length

# REVISED uhf_rfid/protocols/cph/tlv.py -> parse_tlv_sequence

def parse_tlv_sequence(data: bytes) -> Dict[int, Any]:
    """
    Parses a sequence of TLVs from the given data.
    Raises TLVParseError if invalid data is encountered.
    """
    parsed_tlvs: Dict[int, Any] = {}
    offset = 0
    while offset < len(data):
        try:
            tag, length, value, consumed = parse_tlv(data[offset:])
        except TLVParseError as e:
             raise TLVParseError(f"Failed parsing TLV sequence at offset {offset}: {e}", tlv_data=data[offset:]) from e

        # --- Specific Parsing Logic based on Tag ---
        # parsed_value: Any # Remove initialization here

        if tag == cph_const.TAG_STATUS and length == 1:
            parsed_value = value[0]
        elif tag == cph_const.TAG_SOFTWARE_VERSION and length == 3:
             # <<< CORRECTED revision index >>>
            parsed_value = {"major": value[0], "minor": value[1], "revision": value[2]}
        elif tag == cph_const.TAG_DEVICE_TYPE and length == 1:
            parsed_value = value[0]
        elif tag == cph_const.TAG_RSSI and length == 1:
            try: parsed_value = struct.unpack('>b', value)[0]
            except struct.error: parsed_value = value[0]
        elif tag == cph_const.TAG_TIME:
            # Parse based on length (prefer 7 bytes)
            if length == 7:
                try:
                    year = struct.unpack('>H', value[0:2])[0]
                    month, day, hour, minute, second = struct.unpack('>BBBBB', value[2:7])
                    parsed_value = {"year": year, "month": month, "day": day, "hour": hour, "minute": minute, "second": second}
                except (struct.error, IndexError) as e: # Add IndexError
                    logger.warning(f"Could not unpack Time value {value.hex()} as 7-byte datetime: {e}. Returning raw bytes.")
                    parsed_value = value
            elif length == 4: # Handle old format? Return as int?
                 logger.warning(f"Received 4-byte Time TLV (Tag 0x{tag:02X}). Parsing as raw integer.")
                 try: parsed_value = struct.unpack('>I', value)[0]
                 except (struct.error, IndexError): parsed_value = value
            else:
                logger.warning(f"Received Time TLV (Tag 0x{tag:02X}) with unexpected length {length}. Returning raw bytes.")
                parsed_value = value
        elif tag == cph_const.TAG_SINGLE_PARAMETER:
             if length < 1: raise TLVParseError(...) # Check length first
             param_type = value[0]
             param_value_bytes = value[1:]
             # Delegate to helper which MUST return a value
             parsed_value = _parse_single_parameter_value(param_type, param_value_bytes)
        elif tag == cph_const.TAG_OPERATION:
             # Delegate to helper which MUST return a value
             parsed_value = _parse_operation_tlv_value(value, length)
        elif tag == cph_const.TAG_SINGLE_TAG:
             # Recursive call returns a dict or raises error
             parsed_value = parse_tlv_sequence(value)
        elif tag == cph_const.TAG_EPC:
             parsed_value = value.hex().upper()
        # --- Handle User/TID/Reserve if needed ---
        elif tag == cph_const.TAG_USER_DATA:
             logger.debug(f"Found User Data TLV (Tag 0x{tag:02X}), returning raw bytes.")
             parsed_value = value # Or parse if needed
        elif tag == cph_const.TAG_TID_DATA:
             logger.debug(f"Found TID Data TLV (Tag 0x{tag:02X}), returning raw bytes.")
             parsed_value = value # Or parse if needed
        elif tag == cph_const.TAG_RESERVE_DATA:
              logger.debug(f"Found Reserve Data TLV (Tag 0x{tag:02X}), returning raw bytes.")
              parsed_value = value # Or parse if needed
        # --- Default for unknown ---
        else:
            logger.debug(f"Unhandled TLV Tag 0x{tag:02X}, returning raw bytes.")
            parsed_value = value

        # Now assign the parsed value
        parsed_tlvs[tag] = parsed_value
        offset += consumed

    return parsed_tlvs

def _parse_single_parameter_value(param_type: int, value_bytes: bytes) -> Dict[str, Any]:
    """Helper to parse the value part of TAG_SINGLE_PARAMETER based on its type."""
    parsed_param: Dict[str, Any] = {"type": param_type, "raw_value": value_bytes}
    try:
        if param_type == cph_const.PARAM_TYPE_POWER:
            # <<< CORRECTED for 1 byte >>>
            if len(value_bytes) != 1:
                raise TLVParseError(f"Power parameter (0x{param_type:02X}) expects 1 byte value, got {len(value_bytes)}.")
            power_val = value_bytes[0] # Read single byte
            parsed_param["value_raw"] = power_val
            # Assuming the value IS the dBm value directly (0-30)
            parsed_param["value_dbm"] = float(power_val)
        elif param_type == cph_const.PARAM_TYPE_BUZZER:
            if len(value_bytes) != 1:
                 raise TLVParseError(f"Buzzer parameter (0x{param_type:02X}) expects 1 byte value, got {len(value_bytes)}.")
            # <<< CORRECTED Logic (0=OFF, 1=ON) >>>
            parsed_param["is_on"] = (value_bytes[0] != 0x00) # True if setting is non-zero (ON)
            parsed_param["setting"] = value_bytes[0] # Store original setting
        elif param_type == cph_const.PARAM_TYPE_TAG_FILTER_TIME:
             if len(value_bytes) != 1:
                 raise TLVParseError(f"Tag Filter Time parameter (0x{param_type:02X}) expects 1 byte value, got {len(value_bytes)}.")
             parsed_param["time_seconds"] = value_bytes[0]
        elif param_type == cph_const.PARAM_TYPE_MODEM:
             if len(value_bytes) != 4:
                  raise TLVParseError(f"Modem parameter (0x{param_type:02X}) expects 4 bytes value, got {len(value_bytes)}.")
             mixer_gain = value_bytes[0]
             if_amp_gain = value_bytes[1]
             threshold = struct.unpack('>H', value_bytes[2:4])[0]
             parsed_param["mixer_gain"] = mixer_gain
             parsed_param["if_amp_gain"] = if_amp_gain
             parsed_param["threshold"] = threshold
        else:
             logger.warning(f"Unhandled parameter type 0x{param_type:02X} within TAG_SINGLE_PARAMETER.")
    except struct.error as e:
         raise TLVParseError(f"Failed to unpack value for parameter type 0x{param_type:02X}: {e}", tlv_data=value_bytes) from e
    except IndexError as e:
         raise TLVParseError(f"Insufficient data for parameter type 0x{param_type:02X}: {e}", tlv_data=value_bytes) from e
    return parsed_param

def _parse_operation_tlv_value(value_bytes: bytes, declared_length: int) -> Dict[str, Any]:
    """Helper to parse the value part of TAG_OPERATION."""
    parsed_op: Dict[str, Any] = {"raw_value": value_bytes}
    # Minimum expected length based on C# code inference (Pwd(4)+Type(1)+Membank(1)+Len(1) = 7)
    min_len_response = 7
    if declared_length < min_len_response:
         raise TLVParseError(f"Operation TLV value length ({declared_length}) is too short (minimum {min_len_response})", tlv_data=value_bytes)

    try:
        # Unpack Password(4s), Type(B), Membank(B), WordCount(B)
        password, op_type, membank, word_count = struct.unpack('>4sBBB', value_bytes[:min_len_response])

        parsed_op["password"] = password # Keep as bytes or hex? bytes is more raw.
        parsed_op["op_type"] = op_type
        parsed_op["membank"] = membank
        parsed_op["word_count"] = word_count

        # Calculate expected data length based on word_count
        expected_data_len = word_count * 2
        actual_data_len = declared_length - min_len_response
        data_bytes = value_bytes[min_len_response:]

        if actual_data_len < expected_data_len:
             # This could happen if word_count is non-zero but no data follows (e.g., read error?)
             logger.warning(f"Operation TLV: Declared word count {word_count} implies {expected_data_len} data bytes, "
                            f"but only {actual_data_len} bytes available after header. Data might be truncated.")
             parsed_op["data"] = data_bytes[:expected_data_len] # Take what's available up to expected
             parsed_op["data_truncated"] = True
        elif actual_data_len > expected_data_len:
             # More data than expected based on word_count. This is weird.
             logger.warning(f"Operation TLV: More data ({actual_data_len} bytes) present than expected "
                           f"based on word count {word_count} ({expected_data_len} bytes). Using only expected length.")
             parsed_op["data"] = data_bytes[:expected_data_len]
             parsed_op["extra_data"] = data_bytes[expected_data_len:]
        else:
             # Length matches exactly
             parsed_op["data"] = data_bytes

        # If it was a read response, 'data' contains the read data.
        # For write/lock responses, 'data' should ideally be empty (actual_data_len == 0).
        if op_type != cph_const.OP_TYPE_READ and parsed_op["data"]:
            logger.warning(f"Operation TLV for op_type {op_type} unexpectedly contained data: {parsed_op['data'].hex()}")

    except struct.error as e:
         raise TLVParseError(f"Failed to unpack Operation TLV value: {e}", tlv_data=value_bytes) from e
    except IndexError as e:
         raise TLVParseError(f"Insufficient data for Operation TLV value: {e}", tlv_data=value_bytes) from e

    return parsed_op
# --- Building Functions ---

def build_tlv(tag: int, value: bytes) -> bytes:
    """Builds a simple TLV structure (1-byte Length field)."""
    length = len(value)
    if length > 255:
        raise ValueError("TLV value length exceeds 255 bytes (1-byte length field).")
    if not (0 <= tag <= 255):
         raise ValueError("TLV tag must be between 0 and 255.")
    return struct.pack('>BB', tag, length) + value

def build_single_parameter_tlv(param_type: int, param_value_bytes: bytes) -> bytes:
    """Builds the TLV structure for TAG_SINGLE_PARAMETER."""
    if not (0 <= param_type <= 255):
         raise ValueError("Parameter type must be between 0 and 255.")
    value = bytes([param_type]) + param_value_bytes
    return build_tlv(cph_const.TAG_SINGLE_PARAMETER, value)

def build_power_parameter_tlv(power_dbm: int) -> bytes: # Input is now int dBm
    """Builds the TLV to set reader power (1 byte value)."""
    # <<< CORRECTED for 1 byte >>>
    if not (0 <= power_dbm <= 30): # Standard range for direct dBm value
         # Allow values up to 255, but warn? Or clamp? Let's allow for now.
         if not (0 <= power_dbm <= 255):
              raise ValueError("Power dBm value must be between 0 and 255 for 1-byte parameter.")
         logger.warning(f"Power value {power_dbm} dBm might be outside typical 0-30 range.")
    value_bytes = bytes([power_dbm]) # Pack single byte
    return build_single_parameter_tlv(cph_const.PARAM_TYPE_POWER, value_bytes)

def build_buzzer_parameter_tlv(turn_on: bool) -> bytes:
    """Builds the TLV to turn the buzzer on (True, value=1) or off (False, value=0)."""
    # <<< CORRECTED Logic (0=OFF, 1=ON) >>>
    setting = 0x01 if turn_on else 0x00
    value_bytes = bytes([setting])
    return build_single_parameter_tlv(cph_const.PARAM_TYPE_BUZZER, value_bytes)

def build_filter_time_parameter_tlv(seconds: int) -> bytes:
    """Builds the TLV to set the tag filtering time."""
    if not (0 <= seconds <= 255):
        raise ValueError("Filter time must be between 0 and 255 seconds.")
    value_bytes = bytes([seconds])
    return build_single_parameter_tlv(cph_const.PARAM_TYPE_TAG_FILTER_TIME, value_bytes)

def build_query_parameter_tlv(param_type: int) -> bytes:
    """Builds the TLV to query a single parameter value."""
    value_bytes = bytes([param_type])
    return build_tlv(cph_const.TAG_SINGLE_PARAMETER, value_bytes)

# ADD to uhf_rfid/protocols/cph/tlv.py

# ... (imports and other functions) ...

def build_operation_tlv(
    op_type: int,
    membank: int,
    word_ptr: int,
    word_count: int,
    password: bytes = b'\x00\x00\x00\x00',
    write_data: Optional[bytes] = None
) -> bytes:
    """
    Builds the TLV structure for TAG_OPERATION (0x08) used in read/write/lock commands,
    following the structure described in the CPH v4.0.3 documentation.

    Args:
        op_type: The operation type (cph_const.OP_TYPE_READ, OP_TYPE_WRITE, etc.).
        membank: The memory bank (cph_const.MEM_BANK_EPC, etc.). For Lock operations,
                 use cph_const.LOCK_TYPE_* constants here.
        word_ptr: The starting word address (0-based).
        word_count: The number of words to read/write. For Lock operations, this is often 0.
        password: The 4-byte access password. Defaults to '0000'.
        write_data: The data to write (only for OP_TYPE_WRITE). Must be `word_count * 2` bytes long.
                    Must be None for Read/Lock/Kill operations.

    Returns:
        The complete TLV bytes (Tag=0x08, Length, Value).

    Raises:
        ValueError: If input parameters are invalid (e.g., wrong password length,
                    mismatched data length for write, data provided for read/lock).
    """
    if len(password) != 4:
        raise ValueError("Access password must be exactly 4 bytes long.")
    if not (0 <= word_ptr <= 0xFFFF):
        raise ValueError("Word pointer address must be between 0 and 65535.")
    if not (0 <= word_count <= 0xFF):
        raise ValueError("Word count must be between 0 and 255.")

    if op_type == cph_const.OP_TYPE_WRITE:
        if write_data is None:
            raise ValueError("Write operation requires 'write_data'.")
        expected_data_len = word_count * 2
        if len(write_data) != expected_data_len:
            raise ValueError(f"Write data length ({len(write_data)}) does not match "
                             f"expected length based on word count ({word_count} words -> {expected_data_len} bytes).")
    elif write_data is not None:
        raise ValueError(f"Write data should not be provided for operation type {op_type}.")

    # Structure from Doc 4.0.3: Password(4) type(1) membank(1) address(2) length(1) [data(L*2)]
    # Fixed part length = 4 + 1 + 1 + 2 + 1 = 9 bytes
    try:
        # Pack the fixed part: Password(4s), Type(B), Membank(B), Address(>H), Length(B)
        value_bytes = struct.pack(
            '>4sBBHB', # Big-endian format string
            password,
            op_type,
            membank,
            word_ptr,
            word_count
        )
    except struct.error as e:
        # This should not happen with the validations above, but good practice
        raise ValueError(f"Failed to pack operation TLV fixed part: {e}") from e

    # Append data if it's a write operation
    if op_type == cph_const.OP_TYPE_WRITE and write_data is not None:
        value_bytes += write_data

    # Build the final TLV structure (Tag=0x08)
    return build_tlv(cph_const.TAG_OPERATION, value_bytes)

# --- NEW TLV Helpers for Complex Parameters ---

def build_ext_params_tlv(params: ExtParams) -> bytes:
    """Builds a TLV for Extended Parameters (TAG_EXT_PARAM)."""
    try:
        param_bytes = params.encode()
        return build_tlv(cph_const.TAG_EXT_PARAM, param_bytes)
    except ValueError as e:
        logger.error(f"Error encoding ExtParams: {e}")
        raise

def parse_ext_params_tlv(data: bytes) -> ExtParams:
    """Parses the value part of an Extended Parameters TLV."""
    try:
        return ExtParams.decode(data)
    except (ValueError, struct.error) as e:
        raise TLVParseError(f"Failed to parse ExtParams TLV value: {e}") from e

# --- Add helpers for other parameter types here later ---
# def build_working_params_tlv(...) -> bytes:
# def parse_working_params_tlv(...) -> WorkingParams:
# ...
def build_working_params_tlv(params: WorkingParams) -> bytes:
    """Builds a TLV for Working Parameters (TAG_WORKING_PARAM)."""
    try:
        param_bytes = params.encode()
        # Assuming TAG_WORKING_PARAM is defined in constants
        return build_tlv(cph_const.TAG_WORKING_PARAM, param_bytes)
    except ValueError as e:
        logger.error(f"Error encoding WorkingParams: {e}")
        raise

def parse_working_params_tlv(data: bytes) -> WorkingParams:
    """Parses the value part of a Working Parameters TLV."""
    try:
        return WorkingParams.decode(data)
    except (ValueError, struct.error) as e:
        raise TLVParseError(f"Failed to parse WorkingParams TLV value: {e}") from e

def build_transport_params_tlv(params: TransportParams) -> bytes:
    """Builds a TLV for Transport Parameters (TAG_TRANSPORT_PARAM)."""
    try:
        param_bytes = params.encode()
        # Assuming TAG_TRANSPORT_PARAM is defined in constants
        return build_tlv(cph_const.TAG_TRANSPORT_PARAM, param_bytes)
    except ValueError as e:
        logger.error(f"Error encoding TransportParams: {e}")
        raise

def parse_transport_params_tlv(data: bytes) -> TransportParams:
    """Parses the value part of a Transport Parameters TLV."""
    try:
        return TransportParams.decode(data)
    except (ValueError, struct.error) as e:
        raise TLVParseError(f"Failed to parse TransportParams TLV value: {e}") from e

def build_advance_params_tlv(params: AdvanceParams) -> bytes:
    """Builds a TLV for Advance Parameters (TAG_ADVANCE_PARAM)."""
    try:
        param_bytes = params.encode()
        # Assuming TAG_ADVANCE_PARAM is defined in constants
        return build_tlv(cph_const.TAG_ADVANCE_PARAM, param_bytes)
    except ValueError as e:
        logger.error(f"Error encoding AdvanceParams: {e}")
        raise

def parse_advance_params_tlv(data: bytes) -> AdvanceParams:
    """Parses the value part of an Advance Parameters TLV."""
    try:
        return AdvanceParams.decode(data)
    except (ValueError, struct.error) as e:
        raise TLVParseError(f"Failed to parse AdvanceParams TLV value: {e}") from e

# --- UPDATING parse_tlv_sequence (Optional Refinement) ---
# We *could* make parse_tlv_sequence smarter to automatically call
# specific parsers based on tag type, but for now, the Reader/Dispatcher
# can handle looking up the tag and calling the specific parser.
# Let's keep parse_tlv_sequence generic for now.

# Example of how parse_tlv_sequence could be made smarter (NOT APPLYING THIS NOW):
# def parse_tlv_sequence(data: bytes) -> Dict[int, Any]:
#    # ... existing loop ...
#    if tag == const.TAG_EXT_PARAM:
#        parsed_value = parse_ext_params_tlv(value_bytes)
#    elif tag == const.TAG_SINGLE_PARAMETER:
#        parsed_value = parse_single_parameter_tlv(value_bytes)
#    # ... other specific tags ...
#    else:
#        # Default to raw bytes or try generic parsing?
#        parsed_value = value_bytes
#    parsed_data[tag] = parsed_value
#    # ... rest of loop ...
#    return parsed_data

# --- build_operation_tlv and other existing helpers ---
# ... (Ensure build_operation_tlv exists and handles data validation) ...