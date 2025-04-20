# tests/protocols/cph/test_cph_protocol.py

import pytest
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import tlv, constants # For tag constants and expected parsed data
from uhf_rfid.protocols import framing # For frame constants and raw frames
from uhf_rfid.core.exceptions import FrameParseError, ChecksumError, TLVParseError, ProtocolError
from uhf_rfid.protocols.cph import constants as cph_const


# --- Test Fixtures ---

@pytest.fixture
def protocol() -> CPHProtocol:
    """Provides a CPHProtocol instance for tests."""
    return CPHProtocol()

# --- Test Data (using data defined in test_framing and test_tlv) ---
# Re-import or re-define necessary test data for clarity if needed
# Example frames:
QUERY_VERSION_CMD_BYTES = bytes.fromhex("524600000040000028")
QUERY_VERSION_RESP_BYTES = bytes.fromhex("524601000040000B0701002003040001210105C5")
TAG_UPLOAD_NOTIF_BYTES = bytes.fromhex("52460200008000195017010CE2000017021701992390217D0501C306043D0000004C")
SET_POWER_CMD_BYTES = bytes.fromhex("524600000048000526030109C424")
SET_POWER_PARAM_TLV = bytes.fromhex("26030109C4")
SET_POWER_RESP_BYTES = bytes.fromhex("524601000048000307010014") # Assuming Status=OK

# Expected parsed parameters (from test_tlv):
STATUS_OK_PARSED = {cph_const.TAG_STATUS: 0x00}
VERSION_RESP_PARAMS_PARSED = {
    cph_const.TAG_STATUS: 0x00,
    cph_const.TAG_SOFTWARE_VERSION: {"major": 4, "minor": 0, "revision": 1},
    cph_const.TAG_DEVICE_TYPE: 5
}
TAG_UPLOAD_PARAMS_PARSED = {
    cph_const.TAG_SINGLE_TAG: { # Nested dictionary
        cph_const.TAG_EPC: "E2000017021701992390217D",
        cph_const.TAG_RSSI: -61, # Parsed signed byte
        cph_const.TAG_TIME: 0x3D000000
    }
}
# ---> ADD THIS DEFINITION <---
PARAM_POWER_SET_PARSED = {
    cph_const.TAG_SINGLE_PARAMETER: {
        "type": cph_const.PARAM_TYPE_POWER,
        "raw_value": bytes.fromhex("09C4"),
        "value_raw": 2500,
        "value_dbm": 25.0
    }
}

# --- Test Cases ---

# 1. Test Command Encoding (encode_command)
@pytest.mark.parametrize("command_code, address, params_data, expected_frame", [
    (0x40, 0x0000, b'', QUERY_VERSION_CMD_BYTES), # Get Version
    (0x48, 0x0000, SET_POWER_PARAM_TLV, SET_POWER_CMD_BYTES), # Set Parameter (Power)
    (0x21, 0x0000, b'', bytes.fromhex("524600000021000047")), # Start Inventory
    (0x80, 0x0102, b'\xAA\xBB', bytes.fromhex("5246000102800002AABB7E")), # Example command 0x80 with address and params
])
def test_encode_command(protocol: CPHProtocol, command_code, address, params_data, expected_frame):
    """Verify command encoding produces correct frames."""
    encoded = protocol.encode_command(command_code, address, params_data)
    assert encoded == expected_frame

# 2. Test Frame Decoding (decode_frame - extracts raw params)
@pytest.mark.parametrize("input_frame, expected_type, expected_addr, expected_code, expected_params_bytes", [
    (QUERY_VERSION_CMD_BYTES, cph_const.FRAME_TYPE_COMMAND, 0x0000, 0x40, b''),
    (QUERY_VERSION_RESP_BYTES, cph_const.FRAME_TYPE_RESPONSE, 0x0000, 0x40, bytes.fromhex("0701002003040001210105")),
    (TAG_UPLOAD_NOTIF_BYTES, cph_const.FRAME_TYPE_NOTIFICATION, 0x0000, 0x80, bytes.fromhex("5017010CE2000017021701992390217D0501C306043D000000")),
    (SET_POWER_RESP_BYTES, cph_const.FRAME_TYPE_RESPONSE, 0x0000, 0x48, bytes.fromhex("070100")),
])
def test_decode_frame_valid(protocol: CPHProtocol, input_frame, expected_type, expected_addr, expected_code, expected_params_bytes):
    """Verify decoding valid frames extracts correct fields and raw parameter bytes."""
    frame_type, address, frame_code, params_data = protocol.decode_frame(input_frame)
    assert frame_type == expected_type
    assert address == expected_addr
    assert frame_code == expected_code
    assert params_data == expected_params_bytes

def test_decode_frame_invalid_checksum(protocol: CPHProtocol):
    """Test decoding frame with bad checksum raises ChecksumError via framing.parse_frame_header."""
    bad_frame = bytearray(QUERY_VERSION_RESP_BYTES)
    bad_frame[-1] = (bad_frame[-1] + 1) % 256 # Corrupt checksum
    with pytest.raises(ChecksumError): # Expect ChecksumError from parse_frame_header
        protocol.decode_frame(bytes(bad_frame))

def test_decode_frame_incomplete(protocol: CPHProtocol):
    """Test decoding incomplete frame raises FrameParseError via framing.parse_frame_header."""
    incomplete_frame = QUERY_VERSION_RESP_BYTES[:-5] # Cut off end
    with pytest.raises(FrameParseError): # Expect FrameParseError from parse_frame_header
        protocol.decode_frame(incomplete_frame)

def test_decode_frame_no_header(protocol: CPHProtocol):
    """Test decoding frame without header raises FrameParseError."""
    no_header_frame = QUERY_VERSION_RESP_BYTES[2:]
    with pytest.raises(FrameParseError, match="does not start with header"):
        protocol.decode_frame(no_header_frame)

# 3. Test Parameter Parsing (parse_parameters - uses tlv module)
@pytest.mark.parametrize("frame_code, frame_type, params_data, expected_parsed_dict", [
    (0x40, cph_const.FRAME_TYPE_RESPONSE, bytes.fromhex("0701002003040001210105"), VERSION_RESP_PARAMS_PARSED), # Query Version Resp
    (0x80, cph_const.FRAME_TYPE_NOTIFICATION, bytes.fromhex("5017010CE2000017021701992390217D0501C306043D000000"), TAG_UPLOAD_PARAMS_PARSED), # Tag Upload Notif
    (0x48, cph_const.FRAME_TYPE_RESPONSE, bytes.fromhex("070100"), STATUS_OK_PARSED), # Set Parameter Resp (Status OK)
    (0x21, cph_const.FRAME_TYPE_RESPONSE, bytes.fromhex("070100"), STATUS_OK_PARSED), # Start Inventory Resp (Status OK)
    (0x23, cph_const.FRAME_TYPE_RESPONSE, bytes.fromhex("070117"), {cph_const.TAG_STATUS: 0x17}), # Stop Inventory Resp (Status Error)
    (cph_const.CMD_QUERY_PARAMETER, cph_const.FRAME_TYPE_RESPONSE, bytes.fromhex("07010026020119"),
     # Status=OK, Param=Power(25)
     {  # Очакван парснат резултат:
         cph_const.TAG_STATUS: cph_const.STATUS_SUCCESS,
         cph_const.TAG_SINGLE_PARAMETER: {
             "type": cph_const.PARAM_TYPE_POWER,
             "raw_value": bytes.fromhex("19"),
             "value_raw": 25,
             "value_dbm": 25.0
         }
     }), # Reuse parsed dict from tlv tests
])
def test_parse_parameters_valid(protocol: CPHProtocol, frame_code, frame_type, params_data, expected_parsed_dict):
    """Verify parsing parameter bytes yields correct structured data."""
    parsed = protocol.parse_parameters(frame_code, frame_type, params_data)
    assert parsed == expected_parsed_dict

def test_parse_parameters_empty(protocol: CPHProtocol):
    """Test parsing empty parameter data returns an empty dict."""
    assert protocol.parse_parameters(0x40, cph_const.FRAME_TYPE_RESPONSE, b'') == {}

def test_parse_parameters_tlv_error(protocol: CPHProtocol):
    """Test that underlying TLVParseError is wrapped in ProtocolError."""
    bad_tlv_data = bytes.fromhex("070200") # Status tag, declares length 2, provides 1 byte
    with pytest.raises(ProtocolError, match="TLV parsing error"):
        protocol.parse_parameters(0x48, cph_const.FRAME_TYPE_RESPONSE, bad_tlv_data)

# 4. Test Checksum Calculation (delegated, but good to have a check here too)
def test_checksum_delegation(protocol: CPHProtocol):
    """Verify the protocol's checksum method delegates correctly."""
    content = QUERY_VERSION_CMD_BYTES[:-1]
    expected = QUERY_VERSION_CMD_BYTES[-1]
    # Check static method access if needed, or instance access
    assert CPHProtocol.calculate_checksum(content) == expected
    assert protocol.calculate_checksum(content) == expected