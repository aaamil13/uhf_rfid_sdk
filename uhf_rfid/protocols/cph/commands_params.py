# uhf_rfid/protocols/cph/commands_params.py
import logging
from typing import Dict, Any, Type, TypeVar

# Use absolute imports
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph import tlv
from uhf_rfid.core.exceptions import ProtocolError

# Import used parameter dataclasses
from .parameters import (
    WorkingParams, ExtParams, TransportParams, AdvanceParams,
    ModbusParams, UsbDataParams, DataFlagParams
)

from ..base_protocol import (
    PARAM_TYPE_POWER, PARAM_TYPE_BUZZER, PARAM_TYPE_TAG_FILTER_TIME,
    PARAM_TYPE_MODEM # Add others if needed
)

logger = logging.getLogger(__name__)

# --- Single Parameters ---

def encode_set_single_param_request(param_type: int, value: Any) -> bytes:
    """ Encodes a request to set a single parameter using TAG_SINGLE_PARAMETER (0x26). """
    if param_type == cph_const.PARAM_TYPE_POWER:
        if not isinstance(value, int) or not (0 <= value <= 33): # Assuming 0-33 dBm range for CPH
             raise ValueError(f"Invalid power value: {value}. Must be int 0-33.")
        param_data = bytes([value])
    elif param_type == cph_const.PARAM_TYPE_BUZZER:
        param_data = bytes([1 if value else 0])
    elif param_type == cph_const.PARAM_TYPE_TAG_FILTER_TIME:
        if not isinstance(value, int) or not (0 <= value <= 255):
             raise ValueError(f"Invalid filter time: {value}. Must be int 0-255.")
        param_data = bytes([value])
    elif param_type == cph_const.PARAM_TYPE_MODEM:
         if not isinstance(value, bytes) or len(value) != 4:
              raise ValueError(f"Invalid modem parameters: {value!r}. Must be 4 bytes.")
         param_data = value
    else:
        logger.error(f"Unsupported single parameter type for set: {param_type}")
        raise ValueError(f"Unsupported single parameter type for set: {param_type}")

    # TAG_SINGLE_PARAMETER expects Type byte followed by Value bytes
    tlv_value = bytes([param_type]) + param_data
    return tlv.build_tlv(cph_const.TAG_SINGLE_PARAMETER, tlv_value)

def encode_query_single_param_request(param_type: int) -> bytes:
    """ Encodes a request to query a single parameter using TAG_SINGLE_PARAMETER (0x26). """
    # Query just sends the parameter type identifier in the TLV value field
    if param_type not in [cph_const.PARAM_TYPE_POWER, cph_const.PARAM_TYPE_BUZZER, cph_const.PARAM_TYPE_TAG_FILTER_TIME, cph_const.PARAM_TYPE_MODEM]:
         logger.error(f"Unsupported single parameter type for query: {param_type}")
         raise ValueError(f"Unsupported single parameter type for query: {param_type}")

    tlv_value = bytes([param_type])
    return tlv.build_tlv(cph_const.TAG_SINGLE_PARAMETER, tlv_value)

def decode_query_single_param_response(param_type: int, parsed_params: Dict[Any, Any]) -> bytes:
    """ Decodes the value of a queried single parameter from TAG_SINGLE_PARAMETER (0x26). """
    if cph_const.TAG_SINGLE_PARAMETER not in parsed_params:
        raise ProtocolError(f"TAG_SINGLE_PARAMETER missing in query response for type {param_type}", frame_part=parsed_params)

    data = parsed_params[cph_const.TAG_SINGLE_PARAMETER]
    if not isinstance(data, bytes) or len(data) < 1:
        raise ProtocolError(f"Invalid data format for TAG_SINGLE_PARAMETER: {data!r}", frame_part=data)

    # First byte should be the parameter type echo
    if data[0] != param_type:
         logger.warning(f"Parameter type mismatch in single param response: Expected {param_type}, got {data[0]}")
         # Continue anyway? Or raise error?
         # raise ProtocolError(f"Parameter type mismatch in response: Expected {param_type}, got {data[0]}", frame_part=data)

    # Return the actual value bytes (following the type byte)
    value_bytes = data[1:]
    logger.debug(f"Decoded single param type {data[0]} value: {value_bytes.hex(' ')}")
    return value_bytes


# --- Complex Parameters (Implement all) ---

def encode_set_ext_params_request(params: ExtParams) -> bytes:
    try:
        encoded_data = params.encode()
        return tlv.build_tlv(cph_const.TAG_EXT_PARAM, encoded_data)
    except Exception as e:
        logger.exception(f"Failed to encode ExtParams: {e}")
        raise ProtocolError(f"Failed to encode ExtParams: {e}") from e

def decode_get_ext_params_response(parsed_params: Dict[Any, Any]) -> ExtParams:
    if cph_const.TAG_EXT_PARAM not in parsed_params:
        raise ProtocolError("Extended Parameters tag (0x29) missing in response", frame_part=parsed_params)
    ext_param_data = parsed_params[cph_const.TAG_EXT_PARAM]
    if not isinstance(ext_param_data, bytes):
        raise ProtocolError(f"Invalid Extended Parameters data format: {ext_param_data!r}", frame_part=ext_param_data)
    try:
        return ExtParams.decode(ext_param_data)
    except Exception as e:
        logger.exception(f"Error parsing Extended Parameters data: {e}")
        raise ProtocolError(f"Error parsing Extended Parameters data: {e}", frame_part=ext_param_data) from e

def encode_set_working_params_request(params: WorkingParams) -> bytes:
     try:
         encoded_data = params.encode()
         return tlv.build_tlv(cph_const.TAG_WORKING_PARAM, encoded_data)
     except Exception as e:
          logger.exception(f"Failed to encode WorkingParams: {e}")
          raise ProtocolError(f"Failed to encode WorkingParams: {e}") from e

def decode_get_working_params_response(parsed_params: Dict[Any, Any]) -> WorkingParams:
     if cph_const.TAG_WORKING_PARAM not in parsed_params:
          raise ProtocolError("Working Parameters tag (0x23) missing in response", frame_part=parsed_params)
     param_data = parsed_params[cph_const.TAG_WORKING_PARAM]
     if not isinstance(param_data, bytes):
          raise ProtocolError(f"Invalid Working Parameters data format: {param_data!r}", frame_part=param_data)
     try:
          return WorkingParams.decode(param_data)
     except Exception as e:
          logger.exception(f"Error parsing Working Parameters data: {e}")
          raise ProtocolError(f"Error parsing Working Parameters data: {e}", frame_part=param_data) from e

def encode_set_transport_params_request(params: TransportParams) -> bytes:
    try:
        encoded_data = params.encode()
        # Check constant: TAG_TRANSPORT_PARAM is 0x24 according to comments, but base_protocol used 0x25? Verify CPH spec. Assuming 0x24 for now.
        return tlv.build_tlv(cph_const.TAG_TRANSPORT_PARAM, encoded_data) 
    except Exception as e:
        logger.exception(f"Failed to encode TransportParams: {e}")
        raise ProtocolError(f"Failed to encode TransportParams: {e}") from e

def decode_get_transport_params_response(parsed_params: Dict[Any, Any]) -> TransportParams:
    # Check constant: TAG_TRANSPORT_PARAM is 0x24? Verify CPH spec.
    if cph_const.TAG_TRANSPORT_PARAM not in parsed_params:
        raise ProtocolError("Transport Parameters tag (0x24) missing in response", frame_part=parsed_params)
    param_data = parsed_params[cph_const.TAG_TRANSPORT_PARAM]
    if not isinstance(param_data, bytes):
        raise ProtocolError(f"Invalid Transport Parameters data format: {param_data!r}", frame_part=param_data)
    try:
        return TransportParams.decode(param_data)
    except Exception as e:
        logger.exception(f"Error parsing Transport Parameters data: {e}")
        raise ProtocolError(f"Error parsing Transport Parameters data: {e}", frame_part=param_data) from e

def encode_set_advance_params_request(params: AdvanceParams) -> bytes:
    try:
        encoded_data = params.encode()
        # Check constant: TAG_ADVANCE_PARAM is 0x25? Verify CPH spec.
        return tlv.build_tlv(cph_const.TAG_ADVANCE_PARAM, encoded_data) 
    except Exception as e:
        logger.exception(f"Failed to encode AdvanceParams: {e}")
        raise ProtocolError(f"Failed to encode AdvanceParams: {e}") from e

def decode_get_advance_params_response(parsed_params: Dict[Any, Any]) -> AdvanceParams:
    # Check constant: TAG_ADVANCE_PARAM is 0x25? Verify CPH spec.
    if cph_const.TAG_ADVANCE_PARAM not in parsed_params:
        raise ProtocolError("Advance Parameters tag (0x25) missing in response", frame_part=parsed_params)
    param_data = parsed_params[cph_const.TAG_ADVANCE_PARAM]
    if not isinstance(param_data, bytes):
        raise ProtocolError(f"Invalid Advance Parameters data format: {param_data!r}", frame_part=param_data)
    try:
        return AdvanceParams.decode(param_data)
    except Exception as e:
        logger.exception(f"Error parsing Advance Parameters data: {e}")
        raise ProtocolError(f"Error parsing Advance Parameters data: {e}", frame_part=param_data) from e

def encode_set_usb_data_params_request(params: UsbDataParams) -> bytes:
    # Assuming CMD_SET_USB_DATA (0x50) uses a TLV wrapping the UsbDataParams.encode()
    # The specific TAG is not defined in constants.py yet. Need CPH spec. Guessing TAG_USB_DATA = 0xYY
    # Placeholder - needs correct TAG from spec
    # TAG_USB_DATA_PARAM = 0x?? # Define this constant
    try:
        encoded_data = params.encode()
        # return tlv.build_tlv(cph_const.TAG_USB_DATA_PARAM, encoded_data)
        raise NotImplementedError("TAG for USB Data Params not defined in constants")
    except Exception as e:
        logger.exception(f"Failed to encode UsbDataParams: {e}")
        raise ProtocolError(f"Failed to encode UsbDataParams: {e}") from e

def decode_get_usb_data_params_response(parsed_params: Dict[Any, Any]) -> UsbDataParams:
    # Assuming CMD_QUERY_USB_DATA (0x51) returns a TLV wrapping the data
    # Placeholder - needs correct TAG from spec
    # TAG_USB_DATA_PARAM = 0x??
    # if cph_const.TAG_USB_DATA_PARAM not in parsed_params:
    #     raise ProtocolError("USB Data Parameters tag missing in response", frame_part=parsed_params)
    # param_data = parsed_params[cph_const.TAG_USB_DATA_PARAM]
    # if not isinstance(param_data, bytes):
    #     raise ProtocolError(f"Invalid USB Data Parameters data format: {param_data!r}", frame_part=param_data)
    try:
        # return UsbDataParams.decode(param_data)
        raise NotImplementedError("TAG for USB Data Params not defined in constants or decode logic missing")
    except Exception as e:
        logger.exception(f"Error parsing USB Data Parameters data: {e}")
        raise ProtocolError(f"Error parsing USB Data Parameters data: {e}") # from e? Add frame_part?)

def encode_set_data_flag_params_request(params: DataFlagParams) -> bytes:
    # Assuming CMD_SET_DATA_FLAG (0x52) uses a TLV wrapping DataFlagParams.encode()
    # Placeholder - needs correct TAG from spec
    # TAG_DATA_FLAG_PARAM = 0x??
    try:
        encoded_data = params.encode()
        # return tlv.build_tlv(cph_const.TAG_DATA_FLAG_PARAM, encoded_data)
        raise NotImplementedError("TAG for Data Flag Params not defined in constants")
    except Exception as e:
        logger.exception(f"Failed to encode DataFlagParams: {e}")
        raise ProtocolError(f"Failed to encode DataFlagParams: {e}") from e

def decode_get_data_flag_params_response(parsed_params: Dict[Any, Any]) -> DataFlagParams:
    # Assuming CMD_QUERY_DATA_FLAG (0x53) returns a TLV wrapping the data
    # Placeholder - needs correct TAG from spec
    # TAG_DATA_FLAG_PARAM = 0x??
    # if cph_const.TAG_DATA_FLAG_PARAM not in parsed_params:
    #      raise ProtocolError("Data Flag Parameters tag missing in response", frame_part=parsed_params)
    # param_data = parsed_params[cph_const.TAG_DATA_FLAG_PARAM]
    # if not isinstance(param_data, bytes):
    #      raise ProtocolError(f"Invalid Data Flag Parameters data format: {param_data!r}", frame_part=param_data)
    try:
        # return DataFlagParams.decode(param_data)
        raise NotImplementedError("TAG for Data Flag Params not defined in constants or decode logic missing")
    except Exception as e:
        logger.exception(f"Error parsing Data Flag Parameters data: {e}")
        raise ProtocolError(f"Error parsing Data Flag Parameters data: {e}") # from e? Add frame_part?

def encode_set_modbus_params_request(params: ModbusParams) -> bytes:
    # CMD_SET_MODBUS_PARAM (0x54) might use multiple individual TLVs or one wrapper TLV.
    # Assuming individual TLVs based on Reader implementation:
    # TAG_MODBUS_ADDRESS = 0x??, TAG_BAUD_RATE = 0x??, TAG_MODBUS_PARITY = 0x??, TAG_MODBUS_STOP_BITS = 0x??, TAG_MODBUS_PROTOCOL = 0x??
    # Need these TAG constants defined. Placeholder:
    try:
        # tlv_list = []
        # tlv_list.append(tlv.build_tlv(cph_const.TAG_MODBUS_ADDRESS, params.address.to_bytes(1, 'big')))
        # tlv_list.append(tlv.build_tlv(cph_const.TAG_BAUD_RATE, params.baud_rate_code.to_bytes(4, 'big'))) # Assuming 4 bytes for baud rate code
        # tlv_list.append(tlv.build_tlv(cph_const.TAG_MODBUS_PARITY, params.parity_code.to_bytes(1, 'big')))
        # tlv_list.append(tlv.build_tlv(cph_const.TAG_MODBUS_STOP_BITS, params.stop_bits_code.to_bytes(1, 'big')))
        # if params.protocol_code is not None:
        #      tlv_list.append(tlv.build_tlv(cph_const.TAG_MODBUS_PROTOCOL, params.protocol_code.to_bytes(1, 'big')))
        # return b''.join(tlv_list)
        raise NotImplementedError("TAGs for Modbus Params not defined in constants")
    except Exception as e:
        logger.exception(f"Failed to encode ModbusParams: {e}")
        raise ProtocolError(f"Failed to encode ModbusParams: {e}") from e

def decode_get_modbus_params_response(parsed_params: Dict[Any, Any]) -> ModbusParams:
    # CMD_QUERY_MODBUS_PARAM (0x55) likely returns multiple TLVs
    # Need TAG constants defined.
    try:
        # addr = int.from_bytes(parsed_params[cph_const.TAG_MODBUS_ADDRESS], 'big')
        # baud = int.from_bytes(parsed_params[cph_const.TAG_BAUD_RATE], 'big')
        # parity = int.from_bytes(parsed_params[cph_const.TAG_MODBUS_PARITY], 'big')
        # stop = int.from_bytes(parsed_params[cph_const.TAG_MODBUS_STOP_BITS], 'big')
        # proto = None
        # if cph_const.TAG_MODBUS_PROTOCOL in parsed_params:
        #      proto = int.from_bytes(parsed_params[cph_const.TAG_MODBUS_PROTOCOL], 'big')
        # return ModbusParams(address=addr, baud_rate_code=baud, parity_code=parity, stop_bits_code=stop, protocol_code=proto)
        raise NotImplementedError("TAGs for Modbus Params not defined in constants or response structure unknown")
    except KeyError as e:
        logger.error(f"Missing expected Modbus parameter tag: {e}")
        raise ProtocolError(f"Missing expected Modbus parameter tag: {e}", frame_part=parsed_params) from e
    except Exception as e:
        logger.exception(f"Error parsing Modbus Parameters data: {e}")
        raise ProtocolError(f"Error parsing Modbus Parameters data: {e}", frame_part=parsed_params) from e 