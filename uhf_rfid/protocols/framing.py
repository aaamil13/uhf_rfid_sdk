# uhf_rfid/protocols/framing.py

import struct
from typing import Tuple, Optional


# --- Import constants ---
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.core.exceptions import FrameParseError, ChecksumError

# --- Checksum Calculation (as defined in section 1.3) ---

def calculate_checksum(data: bytes) -> int:
    """
    Calculates the CPH protocol checksum for the given data buffer.

    The checksum is calculated by summing all bytes from the Header
    up to (but not including) the checksum byte itself. The result is
    the two's complement of the sum.

    Args:
        data: The byte sequence (Header through Parameters).

    Returns:
        The calculated checksum byte (as an integer 0-255).
    """
    check_sum = sum(data) & 0xFF
    check_sum = (~check_sum + 1) & 0xFF
    return check_sum

# --- Frame Building ---

def build_frame(
    frame_type: int,
    address: int,
    frame_code: int,
    parameters: bytes = b''
) -> bytes:
    """
    Constructs a complete CPH protocol frame.

    Args:
        frame_type: The type of the frame (0x00, 0x01, or 0x02).
        address: The device address (0x0000 to 0xFFFF).
        frame_code: The command or notification code.
        parameters: The parameter data (bytes), often TLV encoded. Defaults to empty bytes.

    Returns:
        The complete byte frame including header and calculated checksum.

    Raises:
        ValueError: If input parameters are outside their valid ranges.
    """
    if not (0 <= frame_type <= 2):
        raise ValueError(f"Invalid frame_type: {frame_type}. Must be 0, 1, or 2.")
    if not (0x0000 <= address <= 0xFFFF):
        raise ValueError(f"Invalid address: {address}. Must be between 0x0000 and 0xFFFF.")
    if not (0x00 <= frame_code <= 0xFF):
        raise ValueError(f"Invalid frame_code: {frame_code}. Must be between 0x00 and 0xFF.")

    param_len = len(parameters)
    if not (0x0000 <= param_len <= 0xFFFF):
         # Technically possible with large params, though maybe unlikely in practice
        raise ValueError(f"Parameter length {param_len} exceeds maximum allowed (65535 bytes).")

    # Pack the fixed-length fields using struct
    # > = Big-endian
    # B = Unsigned char (1 byte)
    # H = Unsigned short (2 bytes)
    # Construct the frame *without* the checksum first
    # --- Use constants from cph_const ---
    frame_without_checksum = struct.pack(
        '>2sBHBH',
        cph_const.FRAME_HEADER, # Use imported constant
        frame_type,
        address,
        frame_code,
        param_len
    ) + parameters

    checksum = calculate_checksum(frame_without_checksum)
    full_frame = frame_without_checksum + struct.pack('>B', checksum)
    return full_frame

# --- Frame Parsing (Basic) ---
def parse_frame_header(data: bytes) -> Tuple[int, int, int, int, bytes, int, int]: # Added start_index to return tuple signature
    # --- Use constants from cph_const ---
    if not data or len(data) < cph_const.MIN_FRAME_LENGTH: # Use imported constant
        raise FrameParseError(f"Data length {len(data)} is less than minimum frame length {cph_const.MIN_FRAME_LENGTH}.", frame_part=data)

    start_index = data.find(cph_const.FRAME_HEADER) # Use imported constant
    if start_index == -1:
        raise FrameParseError(f"Frame header '{cph_const.FRAME_HEADER.decode()}' not found.", frame_part=data)

    if len(data) < start_index + cph_const.MIN_FRAME_LENGTH: # Use imported constant
         raise FrameParseError(
             f"Insufficient data after header found at index {start_index}. "
             f"Need {cph_const.MIN_FRAME_LENGTH} bytes, found {len(data) - start_index}.",
             frame_part=data[start_index:]
         )

    frame_start_ptr = start_index
    header_end_ptr = (
        frame_start_ptr + cph_const.HEADER_LENGTH + cph_const.FRAME_TYPE_LENGTH +
        cph_const.ADDRESS_LENGTH + cph_const.FRAME_CODE_LENGTH +
        cph_const.PARAM_LENGTH_FIELD_LENGTH
    ) # Use imported constants

    try:
        # --- Use constant for header length in unpack ---
        _, frame_type, address, frame_code, declared_param_len = struct.unpack(
            '>2sBHBH',
            data[frame_start_ptr : header_end_ptr]
        )
    except struct.error as e:
        raise FrameParseError(f"Failed to unpack header fields: {e}", frame_part=data[frame_start_ptr:header_end_ptr]) from e

    # --- Use constants for lengths ---
    expected_total_length = (
        header_end_ptr - frame_start_ptr +
        declared_param_len + cph_const.CHECKSUM_LENGTH
    ) # Use imported constant

    if len(data) < frame_start_ptr + expected_total_length:
        raise FrameParseError(
            f"Incomplete frame. Declared param length {declared_param_len} "
            f"plus headers/checksum requires {expected_total_length} bytes, "
            f"but only {len(data) - frame_start_ptr} bytes available after header start.",
            frame_part=data[start_index:]
        )

    full_frame_data = data[frame_start_ptr : frame_start_ptr + expected_total_length]
    frame_content = full_frame_data[:-cph_const.CHECKSUM_LENGTH] # Use imported constant
    received_checksum = full_frame_data[-cph_const.CHECKSUM_LENGTH] # Use imported constant

    calculated_checksum = calculate_checksum(frame_content)
    if calculated_checksum != received_checksum:
        raise ChecksumError(calculated_checksum, received_checksum, full_frame_data)

    param_start_ptr = header_end_ptr
    param_end_ptr = param_start_ptr + declared_param_len
    parameters = frame_content[param_start_ptr - frame_start_ptr : param_end_ptr - frame_start_ptr]

    return frame_type, address, frame_code, declared_param_len, parameters, expected_total_length, start_index

def find_and_parse_frame(buffer: bytearray) -> Optional[Tuple[int, int, int, bytes, int]]:
    # --- Use constants from cph_const ---
    if len(buffer) < cph_const.MIN_FRAME_LENGTH: # Use imported constant
        return None

    try:
        frame_type, address, frame_code, _, parameters, consumed_length, start_index = parse_frame_header(bytes(buffer))
        del buffer[:start_index + consumed_length]
        return frame_type, address, frame_code, parameters, consumed_length
    except (FrameParseError, ChecksumError) as e:
        start_index = buffer.find(cph_const.FRAME_HEADER) # Use imported constant
        if start_index != -1:
            # Simplified recovery: discard up to end of found header 'RF'
            print(f"Frame error encountered: {e}. Discarding {start_index + cph_const.HEADER_LENGTH} bytes from buffer start.") # Use constant
            del buffer[:start_index + cph_const.HEADER_LENGTH] # Use constant
        else:
            print(f"Frame error encountered: {e}. No header found or error before header. Buffer unchanged.")
        return None
    except ValueError:
        return None