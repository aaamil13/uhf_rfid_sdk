# uhf_rfid/protocols/cph/commands_device.py
import datetime
import logging
from typing import Dict, Any

# Use absolute imports
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph import tlv
from uhf_rfid.protocols.base_protocol import DeviceInfo
from uhf_rfid.core.exceptions import ProtocolError

logger = logging.getLogger(__name__)

def encode_reboot_request() -> bytes:
    # Reboot command typically has no parameters
    return b''

def encode_get_version_request() -> bytes:
    # Get version command typically has no parameters
    return b''

def decode_get_version_response(parsed_params: Dict[Any, Any]) -> DeviceInfo:
    """ Decodes parsed CPH response parameters into a standard DeviceInfo object. """
    sw_version_bytes = parsed_params.get(cph_const.TAG_SOFTWARE_VERSION)
    hw_version_bytes = parsed_params.get(cph_const.TAG_DEVICE_TYPE) # CPH uses device type tag

    sw_version = sw_version_bytes.decode('ascii', errors='replace') if sw_version_bytes else "N/A"
    hw_version = hw_version_bytes.decode('ascii', errors='replace') if hw_version_bytes else "N/A"

    # CPH protocol doesn't directly provide manufacturer, model, serial
    # They might be part of the device type string or require separate commands.
    return DeviceInfo(software_version=sw_version, hardware_version=hw_version)

def encode_set_rtc_request(time_to_set: datetime.datetime) -> bytes:
    """ Encodes datetime into CPH 7-byte format (YY YY MM DD HH MM SS) TLV. """
    try:
        # Ensure year is within reasonable bounds if needed, though struct might handle it
        if not (2000 <= time_to_set.year <= 9999): # Example validation
             raise ValueError(f"Year {time_to_set.year} out of typical CPH range")

        year_high = (time_to_set.year >> 8) & 0xFF
        year_low = time_to_set.year & 0xFF
        time_bytes = bytes([
            year_high, year_low,
            time_to_set.month, time_to_set.day,
            time_to_set.hour, time_to_set.minute, time_to_set.second
        ])
        return tlv.build_tlv(cph_const.TAG_TIME, time_bytes)
    except (ValueError, TypeError) as e:
        logger.error(f"Error encoding RTC time {time_to_set}: {e}")
        raise ProtocolError(f"Invalid datetime object for CPH encoding: {e}") from e
    except Exception as e:
         logger.exception(f"Unexpected error encoding RTC time: {e}")
         raise ProtocolError(f"Unexpected error encoding RTC time: {e}") from e

def decode_get_rtc_response(parsed_params: Dict[Any, Any]) -> datetime.datetime:
    """ Decodes CPH 7-byte format from TAG_TIME TLV in parsed response. """
    if cph_const.TAG_TIME not in parsed_params:
        raise ProtocolError("RTC time tag (0x06) missing in response")
    time_data = parsed_params[cph_const.TAG_TIME]

    if not isinstance(time_data, bytes) or len(time_data) != 7:
        raise ProtocolError(f"Invalid RTC time data format: Expected 7 bytes, got {time_data!r}")

    try:
        year_high, year_low, month, day, hour, minute, second = time_data
        year = (year_high << 8) | year_low

        # Perform basic validation on decoded values
        if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            raise ValueError(f"Invalid date/time values decoded: Y={year}, M={month}, D={day}, H={hour}, M={minute}, S={second}")

        return datetime.datetime(year, month, day, hour, minute, second)
    except ValueError as e:
        logger.error(f"Error parsing RTC time data ({time_data.hex(' ')}): {e}")
        raise ProtocolError(f"Error parsing RTC time data: {e}") from e
    except Exception as e:
         logger.exception(f"Unexpected error parsing RTC time data: {e}")
         raise ProtocolError(f"Unexpected error parsing RTC time data: {e}") from e 