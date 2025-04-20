# tests/protocols/cph/test_tlv.py

import pytest
import struct
from uhf_rfid.protocols.cph import tlv # Module to test
from uhf_rfid.core.exceptions import TLVParseError
# Import constants for tags, types, etc.
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph.tlv import build_single_parameter_tlv

# --- Updated Test Data ---

# Status TLV (OK)
STATUS_OK_BYTES = bytes.fromhex("070100")
STATUS_OK_PARSED = {cph_const.TAG_STATUS: cph_const.STATUS_SUCCESS}

# Software Version TLV
VERSION_BYTES = bytes.fromhex("2003040001")
VERSION_PARSED = {cph_const.TAG_SOFTWARE_VERSION: {"major": 4, "minor": 0, "revision": 1}}

# Device Type TLV
DEVTYPE_BYTES = bytes.fromhex("210105")
DEVTYPE_PARSED = {cph_const.TAG_DEVICE_TYPE: 5}

# --- CORRECTED Parameter TLVs ---
# Single Parameter TLV (Set Power 25 dBm = 0x19) - Now 1 byte value
PARAM_POWER_SET_BYTES = bytes.fromhex("26020119") # Tag=26, Len=2, Val=Type(01)+Value(19)
PARAM_POWER_SET_PARSED = {
    cph_const.TAG_SINGLE_PARAMETER: {
        "type": cph_const.PARAM_TYPE_POWER,
        "raw_value": bytes.fromhex("19"),
        "value_raw": 25,
        "value_dbm": 25.0 # Assuming direct dBm value
    }
}

# Single Parameter TLV (Set Buzzer ON = 0x01) - Corrected logic 0=OFF, 1=ON
PARAM_BUZZER_ON_BYTES = bytes.fromhex("26020201") # Tag=26, Len=2, Val=Type(02)+Value(01)
PARAM_BUZZER_ON_PARSED = {
    cph_const.TAG_SINGLE_PARAMETER: {
        "type": cph_const.PARAM_TYPE_BUZZER,
        "raw_value": bytes.fromhex("01"),
        "is_on": True,
        "setting": 0x01
    }
}
# Single Parameter TLV (Set Buzzer OFF = 0x00) - Corrected logic
PARAM_BUZZER_OFF_BYTES = bytes.fromhex("26020200") # Tag=26, Len=2, Val=Type(02)+Value(00)
PARAM_BUZZER_OFF_PARSED = {
    cph_const.TAG_SINGLE_PARAMETER: {
        "type": cph_const.PARAM_TYPE_BUZZER,
        "raw_value": bytes.fromhex("00"),
        "is_on": False,
        "setting": 0x00
    }
}

# Single Parameter TLV (Query Power)
PARAM_POWER_QUERY_BYTES = bytes.fromhex("260101") # Tag=26, Len=1, Val=Type(01)

# Single Parameter TLV (Modem Settings Example - unchanged)
PARAM_MODEM_BYTES = bytes.fromhex("260504092400A0") # Tag=26, Len=5, Val=Type(04)+Value(4 bytes)
PARAM_MODEM_PARSED = {
    cph_const.TAG_SINGLE_PARAMETER: {
        "type": cph_const.PARAM_TYPE_MODEM,
        "raw_value": bytes.fromhex("092400A0"),
        "mixer_gain": 0x09,
        "if_amp_gain": 0x24,
        "threshold": 0x00A0
    }
}

# --- NEW Test Data for Operation TLV (0x08) ---
# Example: Read EPC bank, ptr=2, count=6, pwd=0000
OP_READ_EPC_PARAMS = {
    "op_type": cph_const.OP_TYPE_READ, "membank": cph_const.MEM_BANK_EPC,
    "word_ptr": 2, "word_count": 6, "password": b'\x00\x00\x00\x00'
}
# Value = Pwd(4) + Type(1) + Bank(1) + Ptr(2) + Count(1) = 9 bytes
OP_READ_EPC_VALUE_BYTES = bytes.fromhex("00000000 00 01 0002 06")
OP_READ_EPC_TLV_BYTES = bytes([cph_const.TAG_OPERATION, 9]) + OP_READ_EPC_VALUE_BYTES

# Example: Write User bank, ptr=0, count=2, pwd=11223344, data=AABBCCDD
OP_WRITE_USER_PARAMS = {
    "op_type": cph_const.OP_TYPE_WRITE, "membank": cph_const.MEM_BANK_USER,
    "word_ptr": 0, "word_count": 2, "password": bytes.fromhex("11223344"),
    "write_data": bytes.fromhex("AABBCCDD")
}
# Value = Pwd(4) + Type(1) + Bank(1) + Ptr(2) + Count(1) + Data(4) = 13 bytes
OP_WRITE_USER_VALUE_BYTES = bytes.fromhex("11223344 01 03 0000 02 AABBCCDD")
OP_WRITE_USER_TLV_BYTES = bytes([cph_const.TAG_OPERATION, 13]) + OP_WRITE_USER_VALUE_BYTES

# Example: Operation TLV received in Read Response (Pwd(4)+Type(1)+Bank(1)+Count(1)+Data(N))
OP_READ_RESP_VALUE_BYTES = bytes.fromhex("00000000 00 01 06 E2000017021701992390217D") # Pwd,Type,Bank,Count,Data
OP_READ_RESP_TLV_BYTES = bytes([cph_const.TAG_OPERATION, len(OP_READ_RESP_VALUE_BYTES)]) + OP_READ_RESP_VALUE_BYTES
OP_READ_RESP_PARSED = {
    cph_const.TAG_OPERATION: {
        "password": b'\x00\x00\x00\x00',
        "op_type": cph_const.OP_TYPE_READ,
        "membank": cph_const.MEM_BANK_EPC,
        "word_count": 6,
        "data": bytes.fromhex("E2000017021701992390217D"),
        "raw_value": OP_READ_RESP_VALUE_BYTES # Keep raw value for debugging
    }
}


# Single Tag TLV Container (unchanged, but uses constants)
TAG_CONTAINER_VALUE_BYTES = bytes.fromhex("010CE2000017021701992390217D0501C306043D000000") # Assuming old 4-byte time format in this specific example data
TAG_CONTAINER_TLV_BYTES = bytes([cph_const.TAG_SINGLE_TAG, len(TAG_CONTAINER_VALUE_BYTES)]) + TAG_CONTAINER_VALUE_BYTES
TAG_CONTAINER_PARSED = {
    cph_const.TAG_SINGLE_TAG: { # Nested dictionary
        cph_const.TAG_EPC: "E2000017021701992390217D",
        cph_const.TAG_RSSI: -61,
        # <<< CORRECTED: Expect int for 4-byte time >>>
        cph_const.TAG_TIME: 0x3D000000
    }
}

# --- Test Cases ---

# 1. Test Basic TLV Parsing (parse_tlv) - Updated Power/Buzzer examples
@pytest.mark.parametrize("input_bytes, expected_tag, expected_len, expected_value, expected_consumed", [
    (STATUS_OK_BYTES, cph_const.TAG_STATUS, 1, b'\x00', 3),
    (VERSION_BYTES, cph_const.TAG_SOFTWARE_VERSION, 3, b'\x04\x00\x01', 5),
    (PARAM_POWER_SET_BYTES, cph_const.TAG_SINGLE_PARAMETER, 2, b'\x01\x19', 4), # Corrected Len/Consumed
    (PARAM_BUZZER_ON_BYTES, cph_const.TAG_SINGLE_PARAMETER, 2, b'\x02\x01', 4), # Corrected Len/Consumed
    (TAG_CONTAINER_TLV_BYTES, cph_const.TAG_SINGLE_TAG, 0x17, TAG_CONTAINER_VALUE_BYTES, 2 + 0x17),
    (OP_READ_EPC_TLV_BYTES, cph_const.TAG_OPERATION, 9, OP_READ_EPC_VALUE_BYTES, 11), # Test Operation TLV
    (OP_WRITE_USER_TLV_BYTES, cph_const.TAG_OPERATION, 13, OP_WRITE_USER_VALUE_BYTES, 15),# Test Operation TLV
])
def test_parse_tlv_valid(input_bytes, expected_tag, expected_len, expected_value, expected_consumed):
    """Verify parsing single valid TLVs."""
    tag, length, value, consumed = tlv.parse_tlv(input_bytes)
    assert tag == expected_tag
    assert length == expected_len
    assert value == expected_value
    assert consumed == expected_consumed

def test_parse_tlv_insufficient_header():
    """Test parsing data too short for TLV header."""
    with pytest.raises(TLVParseError, match="Insufficient data for TLV header"):
        tlv.parse_tlv(b'\x07')

def test_parse_tlv_insufficient_value():
    """Test parsing when declared length exceeds available data."""
    bad_data = b'\x20\x05\x01\x02\x03' # Declares len 5, provides 3 bytes value
    with pytest.raises(TLVParseError, match="exceeds available data"):
        tlv.parse_tlv(bad_data)

# 2. Test TLV Sequence Parsing (parse_tlv_sequence) - Updated Power/Buzzer, added Operation
@pytest.mark.parametrize("input_bytes, expected_dict", [
    (STATUS_OK_BYTES, STATUS_OK_PARSED),
    (VERSION_BYTES, VERSION_PARSED),
    (DEVTYPE_BYTES, DEVTYPE_PARSED),
    (PARAM_POWER_SET_BYTES, PARAM_POWER_SET_PARSED), # Corrected
    (PARAM_BUZZER_ON_BYTES, PARAM_BUZZER_ON_PARSED), # Corrected
    (PARAM_BUZZER_OFF_BYTES, PARAM_BUZZER_OFF_PARSED), # Corrected
    (PARAM_MODEM_BYTES, PARAM_MODEM_PARSED),
    (TAG_CONTAINER_TLV_BYTES, TAG_CONTAINER_PARSED),
    (OP_READ_RESP_TLV_BYTES, OP_READ_RESP_PARSED), # Test parsing read response Op TLV
    # Sequence: Status OK + Power Param (25dBm)
    (STATUS_OK_BYTES + PARAM_POWER_SET_BYTES, {**STATUS_OK_PARSED, **PARAM_POWER_SET_PARSED}),
])
def test_parse_tlv_sequence_valid(input_bytes, expected_dict):
    """Verify parsing sequences of TLVs and specific types."""
    parsed = tlv.parse_tlv_sequence(input_bytes)
    assert parsed == expected_dict

def test_parse_tlv_sequence_empty():
    assert tlv.parse_tlv_sequence(b'') == {}

def test_parse_tlv_sequence_trailing_junk():
    """Test parsing raises error on trailing junk (strict behavior)."""
    input_bytes = STATUS_OK_BYTES + b'\xDE\xAD' # Status OK + junk
    raised_error = False
    try:
        tlv.parse_tlv_sequence(input_bytes)
    except TLVParseError as e:
        raised_error = True
        assert "Failed parsing TLV sequence at offset 3" in str(e)
        assert "Declared TLV length (173)" in str(e)
    except Exception as e:
        pytest.fail(f"Expected TLVParseError but got {type(e)}: {e}")
    assert raised_error, "TLVParseError was not raised when parsing trailing junk"

def test_parse_tlv_sequence_invalid_param_len():
     """Test invalid length inside Single Parameter TLV raises error."""
     # Power param should have 1 byte value, giving 2
     bad_param_power = bytes.fromhex("26030199AA") # Tag=26, Len=3, Val=Type(01)+Value(2 bytes)
     with pytest.raises(TLVParseError, match="expects 1 byte value"):
          tlv.parse_tlv_sequence(bad_param_power)

     # Modem param should have 4 bytes value, giving 3
     bad_param_modem = bytes.fromhex("260404092400") # Tag=26, Len=4, Val=Type(04)+Value(3 bytes)
     with pytest.raises(TLVParseError, match="expects 4 bytes value"):
          tlv.parse_tlv_sequence(bad_param_modem)


import re # Import re module

def test_parse_tlv_sequence_invalid_operation_len():
    """Test invalid length for Operation TLV."""
    bad_op_tlv = bytes.fromhex("0806000000000001") # Len=6, value=Pwd+Type+Bank
    # ---> Използвай регулярен израз (по-гъвкаво) <---
    # re.escape предпазва от специални символи в текста, който търсим
    # '.*' позволява всякакви символи преди и след търсения текст
    expected_pattern = r".*" + re.escape("Operation TLV value length (6) is too short (minimum 7)") + r".*"
    with pytest.raises(TLVParseError, match=expected_pattern):
        tlv.parse_tlv_sequence(bad_op_tlv)

# 3. Test TLV Building (build_tlv)
@pytest.mark.parametrize("tag, value, expected_bytes", [
     (cph_const.TAG_STATUS, b'\x00', STATUS_OK_BYTES),
     (cph_const.TAG_SOFTWARE_VERSION, b'\x04\x00\x01', VERSION_BYTES),
])
def test_build_tlv_valid(tag, value, expected_bytes):
     built = tlv.build_tlv(tag, value)
     assert built == expected_bytes

def test_build_tlv_value_too_long():
     with pytest.raises(ValueError, match="exceeds 255 bytes"):
          tlv.build_tlv(0x01, b'\x00' * 256)

# 4. Test Specific Parameter TLV Builders - Corrected
def build_power_parameter_tlv(power_dbm: int) -> bytes:
    """Builds the TLV to set reader power (1 byte value, 0-30 dBm)."""
    if not (0 <= power_dbm <= 30):
        # Тази проверка ТРЯБВА да хвърли ValueError
        raise ValueError("Power dBm value must be between 0 and 30.")
    value_bytes = bytes([power_dbm])
    return build_single_parameter_tlv(cph_const.PARAM_TYPE_POWER, value_bytes)


def test_build_buzzer_parameter_tlv():
     """Test the corrected buzzer parameter builder (0=OFF, 1=ON)."""
     assert tlv.build_buzzer_parameter_tlv(turn_on=True) == PARAM_BUZZER_ON_BYTES # Should be 26 02 02 01
     assert tlv.build_buzzer_parameter_tlv(turn_on=False) == PARAM_BUZZER_OFF_BYTES # Should be 26 02 02 00

def test_build_query_parameter_tlv():
     assert tlv.build_query_parameter_tlv(cph_const.PARAM_TYPE_POWER) == PARAM_POWER_QUERY_BYTES
     assert tlv.build_query_parameter_tlv(cph_const.PARAM_TYPE_BUZZER) == bytes.fromhex("260102")

# 5. Test Operation TLV Builder
def test_build_operation_tlv_read():
    """Test building Operation TLV for read."""
    built_tlv = tlv.build_operation_tlv(**OP_READ_EPC_PARAMS)
    assert built_tlv == OP_READ_EPC_TLV_BYTES

def test_build_operation_tlv_write():
    """Test building Operation TLV for write."""
    built_tlv = tlv.build_operation_tlv(**OP_WRITE_USER_PARAMS)
    assert built_tlv == OP_WRITE_USER_TLV_BYTES

def test_build_operation_tlv_write_length_mismatch():
    """Test ValueError if write data length doesn't match word count."""
    params = OP_WRITE_USER_PARAMS.copy()
    params["write_data"] = b'\xAA\xBB\xCC' # 3 bytes, but word_count=2 (needs 4 bytes)
    with pytest.raises(ValueError, match="does not match expected length"):
        tlv.build_operation_tlv(**params)

def test_build_operation_tlv_data_on_read():
     """Test ValueError if data is provided for read op."""
     params = OP_READ_EPC_PARAMS.copy()
     params["write_data"] = b'\xAA\xBB'
     with pytest.raises(ValueError, match="Write data should not be provided"):
          tlv.build_operation_tlv(**params)

def test_build_operation_tlv_invalid_password():
     """Test ValueError for invalid password length."""
     params = OP_READ_EPC_PARAMS.copy()
     params["password"] = b'\x00\x00'
     with pytest.raises(ValueError, match="password must be exactly 4 bytes"):
         tlv.build_operation_tlv(**params)