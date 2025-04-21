# uhf_rfid/protocols/cph/commands_tags.py
import logging
from typing import Dict, Any, Optional, Union

# Use absolute imports
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph import tlv
from uhf_rfid.core.exceptions import ProtocolError, TLVParseError
from uhf_rfid.protocols.base_protocol import TagReadData

# Constants needed for tag operations (import directly or reference via cph_const)
MEM_BANK_RESERVED = cph_const.MEM_BANK_RESERVED
MEM_BANK_EPC = cph_const.MEM_BANK_EPC
MEM_BANK_TID = cph_const.MEM_BANK_TID
MEM_BANK_USER = cph_const.MEM_BANK_USER

OP_TYPE_READ = cph_const.OP_TYPE_READ
OP_TYPE_WRITE = cph_const.OP_TYPE_WRITE
OP_TYPE_LOCK = cph_const.OP_TYPE_LOCK
OP_TYPE_KILL = cph_const.OP_TYPE_KILL

logger = logging.getLogger(__name__)

# --- Inventory --- 

def encode_start_inventory_request(params: Optional[Any] = None) -> bytes:
    # CPH Start Inventory (CMD_START_INVENTORY 0x21) usually has no parameters.
    # Specific inventory modes (e.g., filtering, session) are typically configured
    # via working parameters (CMD_SET_WORKING_PARAM) or extended parameters
    # (CMD_SET_EXT_PARAM) beforehand.
    # `params` argument is kept for potential future protocol variations but ignored for CPH.
    if params:
        logger.warning("encode_start_inventory_request received parameters, but CPH ignores them.")
    return b''

def encode_active_inventory_request(params: Optional[Any] = None) -> bytes:
    # CPH Active Inventory (CMD_ACTIVE_INVENTORY 0x22) also usually has no parameters.
    # Configuration happens via working/extended params.
    if params:
        logger.warning("encode_active_inventory_request received parameters, but CPH ignores them.")
    return b''

def encode_stop_inventory_request() -> bytes:
    # CPH Stop Inventory (CMD_STOP_INVENTORY 0x23) has no parameters.
    return b''

# --- Tag Memory Access --- 

def _encode_tag_operation_tlv(op_type: int, bank: int, word_ptr: int, word_count: int, password: Optional[bytes], data: Optional[bytes]) -> bytes:
    """ Helper to build the Operation TLV (TAG_OPERATION 0x08). """
    # Validate inputs
    if bank not in [MEM_BANK_RESERVED, MEM_BANK_EPC, MEM_BANK_TID, MEM_BANK_USER]:
        raise ValueError(f"Invalid memory bank: {bank}")
    if word_ptr < 0 or word_ptr > 0xFFFF:
        raise ValueError(f"Word pointer out of range (0-65535): {word_ptr}")
    if word_count <= 0 or word_count > 0xFFFF: # Word count must be positive
         raise ValueError(f"Word count out of range (1-65535): {word_count}")

    op_info = bytearray()
    op_info.append(op_type)
    op_info.append(bank)
    op_info.extend(word_ptr.to_bytes(2, 'big'))
    op_info.extend(word_count.to_bytes(2, 'big')) # Length is in words for read/write

    # Append password (default to 0000 if None)
    if password:
         if len(password) != 4:
              raise ValueError("Access password must be 4 bytes")
         op_info.extend(password)
    else:
         op_info.extend(b'\x00\x00\x00\x00') # Default password

    # Append data only for Write operation
    if op_type == OP_TYPE_WRITE:
        if data is None:
             raise ValueError("Data is required for write operation")
        # Check if data length matches word count (data is in bytes, count in words)
        expected_bytes = word_count * 2
        if len(data) != expected_bytes:
            raise ValueError(f"Data length ({len(data)} bytes) does not match word count ({word_count} words => {expected_bytes} bytes)")
        op_info.extend(data)
    elif data is not None:
         # Ensure data is not provided for non-write ops where it's part of this TLV
         logger.warning("Data provided for non-write operation in _encode_tag_operation_tlv, ignoring.")
         # raise ValueError("Data should not be provided for non-write operations in Operation TLV")

    logger.debug(f"Built Operation TLV: Type={op_type}, Bank={bank}, Ptr={word_ptr}, WC={word_count}, PWD={password.hex() if password else '0000'}, DataLen={len(data) if data else 0}")
    return tlv.build_tlv(cph_const.TAG_OPERATION, bytes(op_info))

def encode_read_tag_memory_request(bank: int, word_ptr: int, word_count: int, password: Optional[bytes] = None) -> bytes:
    """ Encodes request parameters for CMD_READ_TAG (0x31) using Operation TLV. """
    logger.info(f"Encoding Read Tag: Bank={bank}, Ptr={word_ptr}, WC={word_count}, PWD={'****' if password else 'None'}")
    try:
         return _encode_tag_operation_tlv(OP_TYPE_READ, bank, word_ptr, word_count, password, None)
    except ValueError as e:
         logger.error(f"Invalid parameters for read tag memory request: {e}")
         raise ProtocolError(f"Invalid parameters for read tag memory: {e}") from e

def decode_read_tag_memory_response(parsed_params: Dict[Any, Any]) -> bytes:
    """ Decodes the read data from parsed response parameters for CMD_READ_TAG (0x31). """
    # The CPH protocol (v4.0.1) specification indicates that the response to a Read command
    # contains the data within a dedicated TLV corresponding to the memory bank read.
    # - TAG_RESERVE_DATA (0x03) for Reserved bank (contains Access/Kill PWD)
    # - TAG_EPC (0x01) for EPC bank
    # - TAG_TID_DATA (0x04) for TID bank
    # - TAG_USER_DATA (0x02) for User bank
    # The Operation TLV (0x08) is *not* expected in the response according to the doc example.

    # Check in order of likelihood or bank preference
    if cph_const.TAG_USER_DATA in parsed_params:
        data = parsed_params[cph_const.TAG_USER_DATA]
        logger.debug(f"Decoded User data: {data.hex(' ') if isinstance(data, bytes) else data!r}")
        return data if isinstance(data, bytes) else b'' # Ensure bytes

    if cph_const.TAG_EPC in parsed_params:
        # EPC might be returned as parsed string or raw bytes by tlv parser - check spec
        # Assuming raw bytes are desired here.
        epc_data = parsed_params[cph_const.TAG_EPC]
        logger.debug(f"Decoded EPC data: {epc_data!r}")
        if isinstance(epc_data, str):
            # Attempt to convert hex string back to bytes if needed, or handle as error?
            try: return bytes.fromhex(epc_data)
            except ValueError: raise ProtocolError(f"Could not decode EPC string to bytes: {epc_data}")
        return epc_data if isinstance(epc_data, bytes) else b'' # Ensure bytes

    if cph_const.TAG_TID_DATA in parsed_params:
        data = parsed_params[cph_const.TAG_TID_DATA]
        logger.debug(f"Decoded TID data: {data.hex(' ') if isinstance(data, bytes) else data!r}")
        return data if isinstance(data, bytes) else b'' # Ensure bytes

    if cph_const.TAG_RESERVE_DATA in parsed_params:
        data = parsed_params[cph_const.TAG_RESERVE_DATA]
        logger.debug(f"Decoded Reserved data: {data.hex(' ') if isinstance(data, bytes) else data!r}")
        return data if isinstance(data, bytes) else b'' # Ensure bytes

    # If none of the expected data tags are found
    logger.error(f"Could not find expected data TLV (TAG_USER_DATA, TAG_EPC, TAG_TID_DATA, or TAG_RESERVE_DATA) in read tag response. Params: {parsed_params}")
    raise ProtocolError("Could not find read tag data in response", frame_part=parsed_params)

def encode_write_tag_memory_request(bank: int, word_ptr: int, data: bytes, password: Optional[bytes] = None) -> bytes:
    """ Encodes request parameters for CMD_WRITE_TAG (0x30) using Operation TLV. """
    if not data:
        raise ValueError("Data cannot be empty for write operation")
    if len(data) % 2 != 0:
        raise ValueError("Data length must be an even number of bytes (multiple of 16-bit words)")
    word_count = len(data) // 2
    logger.info(f"Encoding Write Tag: Bank={bank}, Ptr={word_ptr}, WC={word_count}, DataLen={len(data)}, PWD={'****' if password else 'None'}")
    try:
        return _encode_tag_operation_tlv(OP_TYPE_WRITE, bank, word_ptr, word_count, password, data)
    except ValueError as e:
         logger.error(f"Invalid parameters for write tag memory request: {e}")
         raise ProtocolError(f"Invalid parameters for write tag memory: {e}") from e

# --- Tag Locking --- 
def encode_lock_tag_request(lock_type: int, password: Optional[bytes] = None) -> bytes:
    """ Encodes request parameters for CMD_LOCK_TAG (0x33) using Operation TLV. """
     # Lock uses TAG_OPERATION (0x08) TLV
     # op_type = OP_TYPE_LOCK (0x02)
     # bank = lock_type (e.g., cph_const.LOCK_TYPE_WRITE_EPC_PERMA)
     # word_ptr = 0 (unused for lock?)
     # word_count = 0 (unused for lock?)
     # password = access password (4 bytes)
     # data = None
     # CPH v4.0.1 Spec confirms: Lock uses Operation TLV (0x08) with OpType=0x02.
     # The 'Bank' field of the Operation TLV holds the specific Lock Type code.
     # Word Pointer and Word Count are specified as 0 for Lock operation.
    logger.info(f"Encoding Lock Tag: LockType=0x{lock_type:02X}, PWD={'****' if password else 'None'}")
    try:
        # word_ptr=0, word_count=0, data=None for lock
        return _encode_tag_operation_tlv(OP_TYPE_LOCK, lock_type, 0, 0, password, None)
    except ValueError as e:
        # Handle potential password length error from helper
        logger.error(f"Invalid password for lock tag request: {e}")
        raise ProtocolError(f"Invalid password for lock tag: {e}") from e

# --- Tag Kill --- 
def encode_kill_tag_request(kill_password: bytes) -> bytes:
    """ Encodes request parameters for CMD_LOCK_TAG (0x33) used for KILL operation. """
    # Kill uses TAG_OPERATION (0x08) TLV
    # op_type = OP_TYPE_KILL (0x03)
    # bank = 0 (Not applicable for kill)
    # word_ptr = 0 (Not applicable for kill)
    # word_count = 0 (Not applicable for kill)
    # password = kill password (4 bytes)
    # data = None
    if not kill_password or len(kill_password) != 4:
        raise ValueError("Kill password must be provided and be exactly 4 bytes")

    logger.info(f"Encoding Kill Tag: PWD={'****'}")
    try:
        # word_ptr=0, word_count=0, bank=0, data=None for kill
        return _encode_tag_operation_tlv(OP_TYPE_KILL, 0, 0, 0, kill_password, None)
    except ValueError as e:
        # Should only be password error here
        logger.error(f"Invalid kill password for kill tag request: {e}")
        raise ProtocolError(f"Invalid kill password for kill tag: {e}") from e

# --- Notifications --- 
def parse_tag_notification_params(params_bytes: bytes) -> TagReadData:
    """ Parses TAG_UPLOADED (0x80) or OFFLINE_TAG_UPLOADED (0x81) parameters. """
    logger.debug(f"Parsing tag notification params: {params_bytes.hex(' ')}")
    try:
        # Tag notifications contain a nested TAG_SINGLE_TAG (0x50)
        parsed_tlvs = tlv.parse_tlv_sequence(params_bytes)
        if cph_const.TAG_SINGLE_TAG not in parsed_tlvs:
            raise TLVParseError("Missing TAG_SINGLE_TAG (0x50) in tag notification")

        tag_data_bytes = parsed_tlvs[cph_const.TAG_SINGLE_TAG]
        if not isinstance(tag_data_bytes, bytes):
             raise TLVParseError(f"Invalid data type for TAG_SINGLE_TAG: {type(tag_data_bytes)}")

        # Parse the inner TLVs within TAG_SINGLE_TAG
        inner_tlvs = tlv.parse_tlv_sequence(tag_data_bytes)
        logger.debug(f"Parsed inner TLVs: {inner_tlvs}")

        # --- Extract required EPC --- 
        epc_val = inner_tlvs.get(cph_const.TAG_EPC)
        if epc_val is None:
             raise TLVParseError("Missing TAG_EPC (0x01) within TAG_SINGLE_TAG")
        # Our tlv parser might return bytes or string for EPC, handle both
        epc_str = epc_val.hex().upper() if isinstance(epc_val, bytes) else str(epc_val).upper()

        # --- Extract optional data --- 
        tid_bytes = inner_tlvs.get(cph_const.TAG_TID_DATA) # TAG 0x04
        tid_str = tid_bytes.hex().upper() if tid_bytes else None

        user_bytes = inner_tlvs.get(cph_const.TAG_USER_DATA) # TAG 0x02

        # RSSI (TAG 0x05) - needs conversion from byte(s) to signed int
        rssi = None
        rssi_val = inner_tlvs.get(cph_const.TAG_RSSI)
        if isinstance(rssi_val, bytes) and len(rssi_val) > 0:
            try:
                # Assuming 1 byte signed integer based on common practice
                rssi = int.from_bytes(rssi_val, 'big', signed=True)
            except Exception as e:
                logger.warning(f"Could not decode RSSI bytes {rssi_val.hex()}: {e}")
        elif isinstance(rssi_val, int):
             rssi = rssi_val # If parser already converted

        # Antenna Number (TAG 0x0A) - needs conversion from byte(s) to int
        antenna = None
        ant_val = inner_tlvs.get(cph_const.TAG_ANT_NO)
        if isinstance(ant_val, bytes) and len(ant_val) > 0:
            try:
                # Assuming 1 byte unsigned integer
                antenna = int.from_bytes(ant_val, 'big', signed=False)
            except Exception as e:
                logger.warning(f"Could not decode Antenna bytes {ant_val.hex()}: {e}")
        elif isinstance(ant_val, int):
             antenna = ant_val # If parser already converted

        # Timestamp might be in TAG_TIME (0x06) inside TAG_SINGLE_TAG or outside? Check CPH spec.
        # Let's assume it *can* be inside for now, but it's often added later.
        timestamp = None
        time_data = inner_tlvs.get(cph_const.TAG_TIME)
        if isinstance(time_data, bytes) and len(time_data) == 7:
            try:
                year_high, year_low, month, day, hour, minute, second = time_data
                year = (year_high << 8) | year_low
                timestamp = datetime.datetime(year, month, day, hour, minute, second)
            except ValueError as e:
                logger.warning(f"Could not parse timestamp {time_data.hex()} in notification: {e}")
        elif time_data:
            logger.warning(f"Ignoring unexpected timestamp format in notification: {time_data!r}")

        tag_read = TagReadData(
            epc=epc_str,
            tid=tid_str,
            user_data=user_bytes,
            rssi=rssi,
            antenna=antenna,
            timestamp=timestamp # May be None if not present or parsable
        )
        logger.debug(f"Successfully parsed tag notification: {tag_read}")
        return tag_read

    except (TLVParseError, ValueError, TypeError) as e:
        logger.error(f"Failed to parse tag notification parameters: {e}")
        raise ProtocolError(f"Failed to parse tag notification parameters: {e}", frame_part=params_bytes) from e
    except Exception as e:
         logger.exception(f"Unexpected error parsing tag notification: {e}")
         raise ProtocolError(f"Unexpected error parsing tag notification: {e}", frame_part=params_bytes) from e 