# uhf_rfid/protocols/cph/commands_misc.py
import logging
from typing import Dict, Any, Union

# Use absolute imports
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph import tlv
from uhf_rfid.core.exceptions import ProtocolError
from .parameters import ModbusParams, UsbDataParams, DataFlagParams # Import needed dataclasses

logger = logging.getLogger(__name__)

# --- Relay --- 
def encode_relay_op_request(relay_state: int) -> bytes:
    """ Encodes request parameters for CMD_RELAY_OP (0x4C) using TAG_RELAY (0x27). """
    # Validate relay_state against known constants
    if relay_state not in [cph_const.RELAY_OFF, cph_const.RELAY_ON, cph_const.RELAY_PULSE]:
        logger.error(f"Invalid relay state provided: {relay_state}")
        raise ValueError(f"Invalid relay state: {relay_state}. Must be RELAY_OFF(0), RELAY_ON(1), or RELAY_PULSE(2).")
    logger.info(f"Encoding Relay Op: State={relay_state}")
    # TAG_RELAY expects 1 byte value
    return tlv.build_tlv(cph_const.TAG_RELAY, bytes([relay_state]))

# --- Audio --- 
def encode_audio_play_request(audio_data: bytes) -> bytes:
    """ Encodes request parameters for CMD_AUDIO_PLAY (0x4D) using TAG_AUDIO_TEXT (0x28). """
    # The command expects the audio data (e.g., text encoded in UTF-8 or GBK, or an index)
    # directly as the value of TAG_AUDIO_TEXT.
    if not audio_data:
        raise ValueError("Audio data cannot be empty")
    logger.info(f"Encoding Audio Play: DataLen={len(audio_data)}")
    return tlv.build_tlv(cph_const.TAG_AUDIO_TEXT, audio_data)

# --- Modbus --- 
def encode_set_modbus_params_request(params: ModbusParams) -> bytes:
    """ Encodes request parameters for CMD_SET_MODBUS_PARAM (0x54). """
    # This command uses multiple individual TLVs according to CPH v4.0.1 spec.
    # Define the required TAG constants if they are missing from constants.py
    TAG_MODBUS_ADDRESS = 0x53 # Spec v4.0.1 Doc (Confirm this) - Reader code used 0x01? No, 0x53 seems right.
    TAG_BAUD_RATE = 0x0B # Spec v4.0.1 Doc (Confirm this)
    TAG_MODBUS_PARITY = 0x54 # Spec v4.0.1 Doc (Confirm this)
    TAG_MODBUS_STOP_BITS = 0x55 # Spec v4.0.1 Doc (Confirm this)
    TAG_MODBUS_PROTOCOL = 0x56 # Spec v4.0.1 Doc (Optional)

    logger.info(f"Encoding Set Modbus Params: Addr={params.address}, Baud={params.baud_rate_code}, Parity={params.parity_code}, Stop={params.stop_bits_code}, Proto={params.protocol_code}")
    try:
        tlv_list = []
        # Address (1 byte)
        if not (0 <= params.address <= 255):
            raise ValueError(f"Invalid Modbus Address: {params.address}")
        tlv_list.append(tlv.build_tlv(TAG_MODBUS_ADDRESS, params.address.to_bytes(1, 'big')))

        # Baud Rate (4 bytes - likely index/code, not actual rate)
        # Assuming the code fits in 4 bytes. Need to validate range if known.
        tlv_list.append(tlv.build_tlv(TAG_BAUD_RATE, params.baud_rate_code.to_bytes(4, 'big')))

        # Parity (1 byte code)
        # Validate parity code if known values exist
        tlv_list.append(tlv.build_tlv(TAG_MODBUS_PARITY, params.parity_code.to_bytes(1, 'big')))

        # Stop Bits (1 byte code)
        # Validate stop bits code if known values exist
        tlv_list.append(tlv.build_tlv(TAG_MODBUS_STOP_BITS, params.stop_bits_code.to_bytes(1, 'big')))

        # Protocol (1 byte code, optional)
        if params.protocol_code is not None:
             # Validate protocol code if known values exist
             tlv_list.append(tlv.build_tlv(TAG_MODBUS_PROTOCOL, params.protocol_code.to_bytes(1, 'big')))

        return b''.join(tlv_list)
    except ValueError as e:
         logger.error(f"Invalid Modbus parameter value: {e}")
         raise ProtocolError(f"Invalid Modbus parameter value: {e}") from e
    except Exception as e:
        logger.exception(f"Failed to encode ModbusParams: {e}")
        raise ProtocolError(f"Failed to encode ModbusParams: {e}") from e

def decode_get_modbus_params_response(parsed_params: Dict[Any, Any]) -> ModbusParams:
    """ Decodes response parameters for CMD_QUERY_MODBUS_PARAM (0x55). """
    # Response contains multiple individual TLVs.
    TAG_MODBUS_ADDRESS = 0x53
    TAG_BAUD_RATE = 0x0B
    TAG_MODBUS_PARITY = 0x54
    TAG_MODBUS_STOP_BITS = 0x55
    TAG_MODBUS_PROTOCOL = 0x56 # Optional

    logger.debug(f"Decoding Get Modbus Params response: {parsed_params}")
    try:
        # Check required tags exist
        required_tags = [TAG_MODBUS_ADDRESS, TAG_BAUD_RATE, TAG_MODBUS_PARITY, TAG_MODBUS_STOP_BITS]
        for tag in required_tags:
            if tag not in parsed_params:
                raise ProtocolError(f"Missing required Modbus parameter tag 0x{tag:02X} in response", frame_part=parsed_params)

        # Extract values (assuming tlv parser returns bytes)
        addr_bytes = parsed_params[TAG_MODBUS_ADDRESS]
        baud_bytes = parsed_params[TAG_BAUD_RATE]
        parity_bytes = parsed_params[TAG_MODBUS_PARITY]
        stop_bytes = parsed_params[TAG_MODBUS_STOP_BITS]

        # Validate lengths
        if len(addr_bytes) != 1: raise ValueError(f"Invalid length for Modbus Address TLV: {len(addr_bytes)}")
        if len(baud_bytes) != 4: raise ValueError(f"Invalid length for Baud Rate TLV: {len(baud_bytes)}")
        if len(parity_bytes) != 1: raise ValueError(f"Invalid length for Parity TLV: {len(parity_bytes)}")
        if len(stop_bytes) != 1: raise ValueError(f"Invalid length for Stop Bits TLV: {len(stop_bytes)}")

        addr = int.from_bytes(addr_bytes, 'big')
        baud_code = int.from_bytes(baud_bytes, 'big')
        parity_code = int.from_bytes(parity_bytes, 'big')
        stop_code = int.from_bytes(stop_bytes, 'big')

        proto_code = None
        if TAG_MODBUS_PROTOCOL in parsed_params:
             proto_bytes = parsed_params[TAG_MODBUS_PROTOCOL]
             if len(proto_bytes) == 1:
                  proto_code = int.from_bytes(proto_bytes, 'big')
             else:
                  logger.warning(f"Invalid length for optional Modbus Protocol TLV: {len(proto_bytes)}, ignoring.")

        return ModbusParams(address=addr, baud_rate_code=baud_code, parity_code=parity_code, stop_bits_code=stop_code, protocol_code=proto_code)

    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error parsing Modbus parameters response: {e}")
        raise ProtocolError(f"Error parsing Modbus Parameters data: {e}", frame_part=parsed_params) from e
    except Exception as e:
        logger.exception(f"Unexpected error parsing Modbus Parameters data: {e}")
        raise ProtocolError(f"Unexpected error parsing Modbus Parameters data: {e}", frame_part=parsed_params) from e

# --- USB Data / Data Flag --- 
# Implement encode/decode functions for UsbDataParams and DataFlagParams
# These will likely require specific TAG constants from CPH spec.

def encode_set_usb_data_params_request(params: UsbDataParams) -> bytes:
    # Placeholder - Needs specific TAG from CPH Spec for CMD_SET_USB_DATA (0x50)
    logger.warning("encode_set_usb_data_params_request not fully implemented - requires TAG definition.")
    # Assuming a wrapper TAG, e.g., TAG_USB_DATA_PARAM = 0x??
    # encoded_data = params.encode()
    # return tlv.build_tlv(cph_const.TAG_USB_DATA_PARAM, encoded_data)
    raise NotImplementedError("TAG for USB Data Params not defined/implemented")

def decode_get_usb_data_params_response(parsed_params: Dict[Any, Any]) -> UsbDataParams:
    # Placeholder - Needs specific TAG from CPH Spec for CMD_QUERY_USB_DATA (0x51) response
    logger.warning("decode_get_usb_data_params_response not fully implemented - requires TAG definition.")
    # Assuming a wrapper TAG, e.g., TAG_USB_DATA_PARAM = 0x??
    # param_data = parsed_params[cph_const.TAG_USB_DATA_PARAM]
    # return UsbDataParams.decode(param_data)
    raise NotImplementedError("TAG for USB Data Params not defined/implemented")

def encode_set_data_flag_params_request(params: DataFlagParams) -> bytes:
    # Placeholder - Needs specific TAG from CPH Spec for CMD_SET_DATA_FLAG (0x52)
    logger.warning("encode_set_data_flag_params_request not fully implemented - requires TAG definition.")
    # Assuming a wrapper TAG, e.g., TAG_DATA_FLAG_PARAM = 0x??
    # encoded_data = params.encode()
    # return tlv.build_tlv(cph_const.TAG_DATA_FLAG_PARAM, encoded_data)
    raise NotImplementedError("TAG for Data Flag Params not defined/implemented")

def decode_get_data_flag_params_response(parsed_params: Dict[Any, Any]) -> DataFlagParams:
    # Placeholder - Needs specific TAG from CPH Spec for CMD_QUERY_DATA_FLAG (0x53) response
    logger.warning("decode_get_data_flag_params_response not fully implemented - requires TAG definition.")
    # Assuming a wrapper TAG, e.g., TAG_DATA_FLAG_PARAM = 0x??
    # param_data = parsed_params[cph_const.TAG_DATA_FLAG_PARAM]
    # return DataFlagParams.decode(param_data)
    raise NotImplementedError("TAG for Data Flag Params not defined/implemented")

# --- Other Misc Commands --- 
# Add functions for CMD_UPLOAD_RECORD_STATUS, CMD_PREPARE_UPDATE, CMD_WRITE_WIEGAND, CMD_VERIFY_TAG if needed 