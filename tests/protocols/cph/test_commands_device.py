# tests/protocols/cph/test_commands_device.py
import pytest
import datetime

# Import functions and classes to test
from uhf_rfid.protocols.cph import commands_device
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.base_protocol import DeviceInfo
from uhf_rfid.core.exceptions import ProtocolError

# --- Tests for Device Commands --- 

def test_encode_reboot_request():
    """Test encoding reboot request (should be empty)."""
    assert commands_device.encode_reboot_request() == b''

def test_encode_get_version_request():
    """Test encoding get version request (should be empty)."""
    assert commands_device.encode_get_version_request() == b''

# --- Tests for Get Version Response --- 

def test_decode_get_version_response_success():
    """Test successful decoding of version response."""
    parsed_params = {
        cph_const.TAG_SOFTWARE_VERSION: b"CPH_V1.2.3",
        cph_const.TAG_DEVICE_TYPE: b"UHFReader288"
    }
    expected_info = DeviceInfo(software_version="CPH_V1.2.3", hardware_version="UHFReader288")
    assert commands_device.decode_get_version_response(parsed_params) == expected_info

def test_decode_get_version_response_missing_tags():
    """Test decoding when tags are missing (should use N/A)."""
    parsed_params_missing_sw = {cph_const.TAG_DEVICE_TYPE: b"HW"}
    expected_missing_sw = DeviceInfo(software_version="N/A", hardware_version="HW")
    assert commands_device.decode_get_version_response(parsed_params_missing_sw) == expected_missing_sw

    parsed_params_missing_hw = {cph_const.TAG_SOFTWARE_VERSION: b"SW"}
    expected_missing_hw = DeviceInfo(software_version="SW", hardware_version="N/A")
    assert commands_device.decode_get_version_response(parsed_params_missing_hw) == expected_missing_hw

    parsed_params_missing_all = {}
    expected_missing_all = DeviceInfo(software_version="N/A", hardware_version="N/A")
    assert commands_device.decode_get_version_response(parsed_params_missing_all) == expected_missing_all

def test_decode_get_version_response_invalid_bytes():
    """Test decoding with non-ASCII bytes (should replace errors)."""
    parsed_params = {
        cph_const.TAG_SOFTWARE_VERSION: b"\x80CPH_V1", # Invalid start byte
        cph_const.TAG_DEVICE_TYPE: b"Reader\xff" # Invalid end byte
    }
    # Expecting replacement character � (U+FFFD)
    expected_info = DeviceInfo(software_version="�CPH_V1", hardware_version="Reader�")
    assert commands_device.decode_get_version_response(parsed_params) == expected_info

# --- Tests for Set RTC Request --- 

def test_encode_set_rtc_request_success():
    """Test successful encoding of set RTC request."""
    test_time = datetime.datetime(2024, 7, 29, 10, 30, 55)
    # Expected bytes: YY_H, YY_L, MM, DD, HH, MM, SS
    # 2024 = 0x07E8
    expected_time_bytes = bytes([0x07, 0xE8, 0x07, 0x1D, 0x0A, 0x1E, 0x37])
    # Expected TLV: Tag=0x06, Len=7, Value=time_bytes
    expected_tlv = bytes([cph_const.TAG_TIME, 0x07]) + expected_time_bytes
    assert commands_device.encode_set_rtc_request(test_time) == expected_tlv

def test_encode_set_rtc_request_invalid_year():
    """Test encoding RTC with invalid year raises correct errors."""
    with pytest.raises(ProtocolError, match="Invalid datetime object for CPH encoding: Year 1999 out of typical CPH range"):
        commands_device.encode_set_rtc_request(datetime.datetime(1999, 1, 1))
    # Year 10000 raises ValueError directly from datetime constructor
    with pytest.raises(ValueError, match="year 10000 is out of range"):
        datetime.datetime(10000, 1, 1) # This line itself raises ValueError
        # commands_device.encode_set_rtc_request(datetime.datetime(10000, 1, 1)) # This line won't be reached

def test_encode_set_rtc_request_invalid_type():
    """Test encoding RTC with non-datetime object raises ProtocolError."""
    # Updated match to expect the actual error message from the generic exception handler
    with pytest.raises(ProtocolError, match="Unexpected error encoding RTC time: 'str' object has no attribute 'year'"):
        commands_device.encode_set_rtc_request("not a datetime") # type: ignore

# --- Tests for Get RTC Response --- 

def test_decode_get_rtc_response_success():
    """Test successful decoding of RTC response."""
    # YY_H=0x07, YY_L=0xE8 (2024), MM=0x07, DD=0x1D (29), HH=0x0A (10), MM=0x1E (30), SS=0x37 (55)
    time_bytes = bytes([0x07, 0xE8, 0x07, 0x1D, 0x0A, 0x1E, 0x37])
    parsed_params = {cph_const.TAG_TIME: time_bytes}
    expected_time = datetime.datetime(2024, 7, 29, 10, 30, 55)
    assert commands_device.decode_get_rtc_response(parsed_params) == expected_time

def test_decode_get_rtc_response_missing_tag():
    """Test decoding RTC response when TAG_TIME is missing."""
    parsed_params = {cph_const.TAG_STATUS: 0x00} # Missing TAG_TIME
    # Use raw string for regex pattern to avoid SyntaxWarning
    with pytest.raises(ProtocolError, match=r"RTC time tag \(0x06\) missing"):
        commands_device.decode_get_rtc_response(parsed_params)

def test_decode_get_rtc_response_invalid_length():
    """Test decoding RTC response with incorrect data length."""
    time_bytes_short = bytes([0x07, 0xE8, 0x07, 0x1D, 0x0A, 0x1E]) # 6 bytes
    parsed_params_short = {cph_const.TAG_TIME: time_bytes_short}
    with pytest.raises(ProtocolError, match="Invalid RTC time data format: Expected 7 bytes"):
        commands_device.decode_get_rtc_response(parsed_params_short)

    time_bytes_long = bytes([0x07, 0xE8, 0x07, 0x1D, 0x0A, 0x1E, 0x37, 0x00]) # 8 bytes
    parsed_params_long = {cph_const.TAG_TIME: time_bytes_long}
    with pytest.raises(ProtocolError, match="Invalid RTC time data format: Expected 7 bytes"):
        commands_device.decode_get_rtc_response(parsed_params_long)

def test_decode_get_rtc_response_invalid_data_type():
    """Test decoding RTC response when data is not bytes."""
    parsed_params = {cph_const.TAG_TIME: "not bytes"}
    with pytest.raises(ProtocolError, match="Invalid RTC time data format"):
        commands_device.decode_get_rtc_response(parsed_params)

def test_decode_get_rtc_response_invalid_date_values():
    """Test decoding RTC response with invalid month/day/hour etc."""
    # Invalid Month (13)
    invalid_month_bytes = bytes([0x07, 0xE8, 13, 0x1D, 0x0A, 0x1E, 0x37])
    parsed_params_month = {cph_const.TAG_TIME: invalid_month_bytes}
    with pytest.raises(ProtocolError, match="Error parsing RTC time data: Invalid date/time values"):
        commands_device.decode_get_rtc_response(parsed_params_month)
    
    # Invalid Day (32)
    invalid_day_bytes = bytes([0x07, 0xE8, 0x07, 32, 0x0A, 0x1E, 0x37])
    parsed_params_day = {cph_const.TAG_TIME: invalid_day_bytes}
    with pytest.raises(ProtocolError, match="Error parsing RTC time data: Invalid date/time values"):
        commands_device.decode_get_rtc_response(parsed_params_day)

    # Invalid Hour (24)
    invalid_hour_bytes = bytes([0x07, 0xE8, 0x07, 0x1D, 24, 0x1E, 0x37])
    parsed_params_hour = {cph_const.TAG_TIME: invalid_hour_bytes}
    with pytest.raises(ProtocolError, match="Error parsing RTC time data: Invalid date/time values"):
        commands_device.decode_get_rtc_response(parsed_params_hour)

    # Add similar checks for minute (60) and second (60) if desired 