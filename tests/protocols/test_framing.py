# tests/protocols/test_framing.py

import pytest # Import pytest
from uhf_rfid.protocols import framing # Import the module to test
from uhf_rfid.core.exceptions import ChecksumError, FrameParseError # Import expected exceptions
from uhf_rfid.protocols.cph import constants as cph_const

# --- Test Data ---

# Example from doc: Query Version Command (2.2)
QUERY_VERSION_CMD_BYTES = bytes.fromhex("524600000040000028")
# ---> ADD THIS DEFINITION <---
QUERY_VERSION_CMD_PARAMS = {
    "frame_type": cph_const.FRAME_TYPE_COMMAND,
    "address": 0x0000,
    "frame_code": 0x40,
    "parameters": b''
}

# Example from doc: Query Version Response (2.2)
QUERY_VERSION_RESP_BYTES = bytes.fromhex("524601000040000B0701002003040001210105C5")
# ---> ADD THIS DEFINITION <---
QUERY_VERSION_RESP_PARAMS = {
    "frame_type": cph_const.FRAME_TYPE_RESPONSE,
    "address": 0x0000,
    "frame_code": 0x40,
    "parameters": bytes.fromhex("0701002003040001210105") # The TLV part
}

# Example from doc: Tag Upload Notification (3.1)
TAG_UPLOAD_NOTIF_BYTES = bytes.fromhex("52460200008000195017010CE2000017021701992390217D0501C306043D0000004C")
# ---> ADD THIS DEFINITION <---
TAG_UPLOAD_NOTIF_PARAMS = {
    "frame_type": cph_const.FRAME_TYPE_NOTIFICATION,
    "address": 0x0000,
    "frame_code": 0x80,
    "parameters": bytes.fromhex("5017010CE2000017021701992390217D0501C306043D000000") # The TLV part
}

# --- Test Cases ---

# 1. Test Checksum Calculation
@pytest.mark.parametrize("frame_content, expected_checksum", [
    (QUERY_VERSION_CMD_BYTES[:-1], QUERY_VERSION_CMD_BYTES[-1]),
    (QUERY_VERSION_RESP_BYTES[:-1], QUERY_VERSION_RESP_BYTES[-1]),
    (TAG_UPLOAD_NOTIF_BYTES[:-1], TAG_UPLOAD_NOTIF_BYTES[-1]),
    (bytes.fromhex("5246000000210000"), 0x47), # Start Inventory Example (Host -> Reader)
    (bytes.fromhex("5246010000210003070100"), 0x3B), # Start Inventory Response (Host <- Reader)
    (bytes.fromhex("524600000048000526030109C4"), 0x24), # Set Power Example
])
def test_calculate_checksum(frame_content, expected_checksum):
    """Verify checksum calculation matches examples."""
    calculated = framing.calculate_checksum(frame_content)
    assert calculated == expected_checksum

# 2. Test Frame Building
@pytest.mark.parametrize("params, expected_bytes", [
    (QUERY_VERSION_CMD_PARAMS, QUERY_VERSION_CMD_BYTES),
    (QUERY_VERSION_RESP_PARAMS, QUERY_VERSION_RESP_BYTES),
    (TAG_UPLOAD_NOTIF_PARAMS, TAG_UPLOAD_NOTIF_BYTES),
])
def test_build_frame(params, expected_bytes):
    """Verify frame building produces the correct byte sequence."""
    built_frame = framing.build_frame(**params)
    assert built_frame == expected_bytes

def test_build_frame_invalid_type():
    """Test building frame with invalid type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid frame_type"):
        framing.build_frame(frame_type=5, address=0, frame_code=0)

def test_build_frame_invalid_address():
    """Test building frame with invalid address raises ValueError."""
    with pytest.raises(ValueError, match="Invalid address"):
        framing.build_frame(frame_type=0, address=0x10000, frame_code=0)

# 3. Test Basic Frame Parsing (parse_frame_header)
@pytest.mark.parametrize("input_bytes, expected_params", [
    (QUERY_VERSION_CMD_BYTES, QUERY_VERSION_CMD_PARAMS),
    (QUERY_VERSION_RESP_BYTES, QUERY_VERSION_RESP_PARAMS),
    (TAG_UPLOAD_NOTIF_BYTES, TAG_UPLOAD_NOTIF_PARAMS),
])
def test_parse_frame_header_valid(input_bytes, expected_params):
    """Verify parsing valid frames extracts correct fields."""
    frame_type, address, frame_code, declared_len, parameters, consumed_len, start_idx = framing.parse_frame_header(input_bytes)
    assert frame_type == expected_params["frame_type"]
    assert address == expected_params["address"]
    assert frame_code == expected_params["frame_code"]
    assert parameters == expected_params["parameters"]
    assert declared_len == len(expected_params["parameters"])
    assert consumed_len == len(input_bytes)
    assert start_idx == 0 # Assumes frame starts at index 0

def test_parse_frame_header_invalid_checksum():
    """Verify parsing with bad checksum raises ChecksumError."""
    bad_frame = bytearray(QUERY_VERSION_CMD_BYTES)
    bad_frame[-1] = (bad_frame[-1] + 1) % 256 # Modify checksum byte
    with pytest.raises(ChecksumError):
        framing.parse_frame_header(bytes(bad_frame))

def test_parse_frame_header_incomplete_frame():
    """Verify parsing incomplete frame raises FrameParseError."""
    # Frame declares 11 bytes params, but only provides some
    incomplete_frame = bytes.fromhex("524601000040000B0701002003C5") # Missing last bytes of params + checksum
    with pytest.raises(FrameParseError, match="Incomplete frame"):
        framing.parse_frame_header(incomplete_frame)

def test_parse_frame_header_short_data():
    """Verify parsing data shorter than minimum frame length raises FrameParseError."""
    short_data = b'RF\x00\x00\x00@'
    with pytest.raises(FrameParseError, match="less than minimum frame length"):
        framing.parse_frame_header(short_data)

def test_parse_frame_header_no_header():
    """Verify parsing data without header 'RF' raises FrameParseError."""
    no_header_data = b'XX\x00\x00\x00\x40\x00\x00\x28'
    with pytest.raises(FrameParseError, match="header 'RF' not found"):
        framing.parse_frame_header(no_header_data)

def test_parse_frame_header_junk_prefix():
    """Verify parsing finds frame after junk prefix."""
    junk_frame = b'\x01\x02\x03' + QUERY_VERSION_CMD_BYTES
    frame_type, address, frame_code, _, parameters, consumed_len, start_idx = framing.parse_frame_header(junk_frame)
    assert frame_type == QUERY_VERSION_CMD_PARAMS["frame_type"]
    assert address == QUERY_VERSION_CMD_PARAMS["address"]
    assert frame_code == QUERY_VERSION_CMD_PARAMS["frame_code"]
    assert parameters == QUERY_VERSION_CMD_PARAMS["parameters"]
    assert start_idx == 3 # Frame found after 3 bytes of junk

# 4. Test Stream Parsing (find_and_parse_frame) - More complex scenarios
def test_find_and_parse_frame_single_valid():
    """Test finding a single valid frame in the buffer."""
    buffer = bytearray(QUERY_VERSION_CMD_BYTES)
    original_len = len(buffer)
    result = framing.find_and_parse_frame(buffer)
    assert result is not None
    frame_type, address, frame_code, parameters, frame_len = result
    assert frame_type == QUERY_VERSION_CMD_PARAMS["frame_type"]
    assert address == QUERY_VERSION_CMD_PARAMS["address"]
    assert frame_code == QUERY_VERSION_CMD_PARAMS["frame_code"]
    assert parameters == QUERY_VERSION_CMD_PARAMS["parameters"]
    assert frame_len == original_len
    assert len(buffer) == 0 # Buffer should be consumed

def test_find_and_parse_frame_junk_prefix():
    """Test finding a frame after junk, consuming buffer correctly."""
    junk = b'\xDE\xAD\xBE\xEF'
    buffer = bytearray(junk + QUERY_VERSION_CMD_BYTES)
    result = framing.find_and_parse_frame(buffer)
    assert result is not None
    assert len(buffer) == 0 # Junk and frame should be consumed

def test_find_and_parse_frame_multiple_valid():
    """Test finding the first of multiple frames."""
    buffer = bytearray(QUERY_VERSION_CMD_BYTES + TAG_UPLOAD_NOTIF_BYTES)
    # Parse first frame
    result1 = framing.find_and_parse_frame(buffer)
    assert result1 is not None
    assert result1[2] == QUERY_VERSION_CMD_PARAMS["frame_code"] # Check frame code
    assert len(buffer) == len(TAG_UPLOAD_NOTIF_BYTES) # First frame consumed
    # Parse second frame
    result2 = framing.find_and_parse_frame(buffer)
    assert result2 is not None
    assert result2[2] == TAG_UPLOAD_NOTIF_PARAMS["frame_code"]
    assert len(buffer) == 0 # Second frame consumed

def test_find_and_parse_frame_incomplete():
    """Test that incomplete frame returns None and doesn't consume buffer."""
    buffer = bytearray(QUERY_VERSION_CMD_BYTES[:-2]) # Missing checksum and last byte
    original_len = len(buffer)
    result = framing.find_and_parse_frame(buffer)
    assert result is None
    assert len(buffer) == original_len # Buffer should be unchanged

def test_find_and_parse_frame_bad_checksum_consumes_header():
     """Test that a frame with bad checksum returns None but consumes the bad header."""
     bad_frame = bytearray(QUERY_VERSION_CMD_BYTES)
     bad_frame[-1] = (bad_frame[-1] + 1) % 256
     buffer = bytearray(b'\x01\x02' + bad_frame) # Junk + bad frame
     original_len = len(buffer)
     result = framing.find_and_parse_frame(buffer)
     assert result is None
     # Expect buffer to contain data *after* the 'RF' header of the bad frame
     assert buffer == bad_frame[len(cph_const.FRAME_HEADER):] # Consumed junk + 'RF'
     # This behavior depends on the chosen recovery strategy in find_and_parse_frame

def test_find_and_parse_frame_no_header():
    """Test that data without header returns None."""
    buffer = bytearray(b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A')
    original_len = len(buffer)
    result = framing.find_and_parse_frame(buffer)
    assert result is None
    assert len(buffer) == original_len # Buffer should be unchanged if no header found