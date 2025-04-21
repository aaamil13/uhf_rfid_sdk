# uhf_rfid/protocols/cph/constants.py

"""
Constants specific to the CPH UHF RFID Communication Protocol v4.0.1.
"""

# --- Frame Structure Constants ---
FRAME_HEADER = b'RF' #{b'RF'}
HEADER_LENGTH = len(FRAME_HEADER)
FRAME_TYPE_LENGTH = 1
ADDRESS_LENGTH = 2
FRAME_CODE_LENGTH = 1
PARAM_LENGTH_FIELD_LENGTH = 2
CHECKSUM_LENGTH = 1
MIN_FRAME_LENGTH = (
    HEADER_LENGTH + FRAME_TYPE_LENGTH + ADDRESS_LENGTH +
    FRAME_CODE_LENGTH + PARAM_LENGTH_FIELD_LENGTH + CHECKSUM_LENGTH
)

# --- Frame Type Constants ---
FRAME_TYPE_COMMAND: int = 0x00
FRAME_TYPE_RESPONSE: int = 0x01
FRAME_TYPE_NOTIFICATION: int = 0x02

# --- Command Frame Code Constants (Host -> Reader) ---
# --- Command Frame Code Constants (Host -> Reader) ---
CMD_REBOOT: int = 0x10
CMD_SET_DEFAULT_PARAM: int = 0x12 # New
CMD_START_INVENTORY: int = 0x21
CMD_ACTIVE_INVENTORY: int = 0x22 # Single burst inventory
CMD_STOP_INVENTORY: int = 0x23
CMD_WRITE_TAG: int = 0x30 # <<< NEW (Write Generic)
CMD_READ_TAG: int = 0x31 # <<< NEW (Read Block)
CMD_WRITE_WIEGAND: int = 0x32 # New (Specific Wiegand write?)
CMD_LOCK_TAG: int = 0x33 # <<< NEW (Lock)
CMD_WRITE_EPC: int = 0x35 # <<< NEW (Write Specific EPC)
CMD_QUERY_EXT_PARAM: int = 0x3E # New
CMD_SET_EXT_PARAM: int = 0x3F # New
CMD_GET_VERSION: int = 0x40 # (Same as Query Device Info)
CMD_SET_WORKING_PARAM: int = 0x41 # New (Complex Set)
CMD_QUERY_WORKING_PARAM: int = 0x42 # New
CMD_QUERY_TRANSPORT_PARAM: int = 0x43 # New
CMD_SET_TRANSPORT_PARAM: int = 0x44 # New
CMD_QUERY_ADVANCE_PARAM: int = 0x45 # New
CMD_SET_ADVANCE_PARAM: int = 0x46 # New
CMD_SET_PARAMETER: int = 0x48 # (Same as Set Single Param)
CMD_QUERY_PARAMETER: int = 0x49 # (Same as Query Single Param)
CMD_QUERY_RTC_TIME: int = 0x4A # New
CMD_SET_RTC_TIME: int = 0x4B # New
CMD_RELAY_OP: int = 0x4C # New
CMD_AUDIO_PLAY: int = 0x4D # New
CMD_VERIFY_TAG: int = 0x4E # New (Possibly for password verification?)
CMD_SET_USB_DATA: int = 0x50 # New
CMD_QUERY_USB_DATA: int = 0x51 # New
CMD_SET_DATA_FLAG: int = 0x52 # New
CMD_QUERY_DATA_FLAG: int = 0x53 # New
CMD_SET_MODBUS_PARAM: int = 0x54 # New
CMD_QUERY_MODBUS_PARAM: int = 0x55 # New
CMD_UPLOAD_RECORD_STATUS: int = 0x72 # New (Response expected?)
CMD_PREPARE_UPDATE: int = 0xF4 # New (Firmware update?)


# --- Notification Frame Code Constants (Reader -> Host) ---
NOTIF_TAG_UPLOADED: int = 0x80
NOTIF_OFFLINE_TAG_UPLOADED: int = 0x81 # New
NOTIF_RECORD_UPLOADED: int = 0x82 # New
NOTIF_HEARTBEAT: int = 0x90 # New

# --- TLV Tag Constants ---
TAG_EPC: int = 0x01
TAG_USER_DATA: int = 0x02 # <<< NEW
TAG_RESERVE_DATA: int = 0x03 # <<< NEW (Likely contains password in read response?)
TAG_TID_DATA: int = 0x04 # <<< NEW
TAG_RSSI: int = 0x05
TAG_TIME: int = 0x06 # Timestamp / RTC Time
TAG_STATUS: int = 0x07
TAG_OPERATION: int = 0x08 # <<< NEW (Operation Info)
TAG_ANT_NO: int = 0x0A # <<< NEW (Antenna Number)
TAG_6B_TAG: int = 0x10 # New (For ISO 18000-6B tags?)
TAG_SOFTWARE_VERSION: int = 0x20
TAG_DEVICE_TYPE: int = 0x21
TAG_WORKING_PARAM: int = 0x23 # New
TAG_TRANSPORT_PARAM: int = 0x24 # New
TAG_ADVANCE_PARAM: int = 0x25 # New
TAG_SINGLE_PARAMETER: int = 0x26
TAG_RELAY: int = 0x27 # New
TAG_AUDIO_TEXT: int = 0x28 # New
TAG_EXT_PARAM: int = 0x29 # New
TAG_SINGLE_TAG: int = 0x50 # Container for nested tag data
TAG_DEVICE_NO: int = 0x52 # <<< NEW (Device Number)
TAG_TEMPERATURE: int = 0x70 # New

# --- Memory Bank Constants (for Operation TLV) ---
MEM_BANK_RESERVED: int = 0x00
MEM_BANK_EPC: int = 0x01
MEM_BANK_TID: int = 0x02
MEM_BANK_USER: int = 0x03

# --- Relay Operation Constants ---
RELAY_OFF: int = 0x00
RELAY_ON: int = 0x01
RELAY_PULSE: int = 0x02 # Speculative value for pulse/toggle

# --- Operation Type Constants (for Operation TLV) ---
OP_TYPE_READ: int = 0x00
OP_TYPE_WRITE: int = 0x01
OP_TYPE_LOCK: int = 0x02
OP_TYPE_KILL: int = 0x03

# --- Lock Type Constants (Membank field values for Lock Operation) ---
LOCK_TYPE_WRITE_EPC_OPEN: int = 0x00       # (Doc value 0 seems wrong, using descriptive names) - Maybe this isn't needed?
LOCK_TYPE_WRITE_EPC_PWD: int = 0x01
LOCK_TYPE_WRITE_EPC_PERMA: int = 0x02
LOCK_TYPE_ACCESS_EPC_OPEN: int = 0x03     # (Unlocks EPC write protection)
LOCK_TYPE_WRITE_USER_PWD: int = 0x04
LOCK_TYPE_WRITE_USER_PERMA: int = 0x05
LOCK_TYPE_ACCESS_USER_OPEN: int = 0x06    # (Unlocks User write protection)
LOCK_TYPE_ACCESS_PWD_PWD: int = 0x07      # (Lock Access Password itself with Access PWD)
LOCK_TYPE_ACCESS_PWD_PERMA: int = 0x08
LOCK_TYPE_ACCESS_ACCESS_OPEN: int = 0x09  # (Unlocks Access Password protection)
LOCK_TYPE_KILL_PWD_PWD: int = 0x0A        # (Lock Kill Password itself with Access PWD)
LOCK_TYPE_KILL_PWD_PERMA: int = 0x0B
LOCK_TYPE_ACCESS_KILL_OPEN: int = 0x0C    # (Unlocks Kill Password protection)


# --- Single Parameter Sub-Type Constants (for TAG_SINGLE_PARAMETER) ---
PARAM_TYPE_POWER: int = 0x01 # Value is 1 byte (0-30 dBm) <<< CORRECTED
PARAM_TYPE_BUZZER: int = 0x02 # Value is 1 byte (0=OFF, 1=ON) <<< CORRECTED
PARAM_TYPE_TAG_FILTER_TIME: int = 0x03 # Value is 1 byte (seconds)
PARAM_TYPE_MODEM: int = 0x04 # Value is 4 bytes (Mixer, IF Gain, Threshold)

# --- Status Code Constants (Value in TAG_STATUS TLV) ---
STATUS_SUCCESS: int = 0x00
STATUS_PARAMETER_UNSUPPORTED: int = 0x14
STATUS_PARAMETER_LEN_ERROR: int = 0x15
STATUS_PARAMETER_CONTEXT_ERROR: int = 0x16
STATUS_UNSUPPORTED_COMMAND: int = 0x17
STATUS_DEVICE_ADDRESS_ERROR: int = 0x18
STATUS_CHECKSUM_ERROR: int = 0x20 # Note: This is a STATUS code, different from ChecksumError exception purpose
STATUS_UNSUPPORTED_TLV_TYPE: int = 0x21
STATUS_FLASH_ERROR: int = 0x22
STATUS_INTERNAL_ERROR: int = 0xFF

# --- Status Code Messages Mapping (Moved from exceptions.py) ---
CPH_STATUS_MESSAGES: dict[int, str] = {
    STATUS_SUCCESS: "SUCCESS: Command completed successfully.",
    STATUS_PARAMETER_UNSUPPORTED: "PARAMETER_UNSUPPORTED: Unsupported parameter type.",
    STATUS_PARAMETER_LEN_ERROR: "PARAMETER_LEN_ERROR: Incorrect parameter length.",
    STATUS_PARAMETER_CONTEXT_ERROR: "PARAMETER_CONTEXT_ERROR: Incorrect parameter content.",
    STATUS_UNSUPPORTED_COMMAND: "UNSUPPORTED_COMMAND: The command code is not supported by the reader.",
    STATUS_DEVICE_ADDRESS_ERROR: "DEVICE_ADDRESS_ERROR: The device address in the command does not match the reader's address.",
    STATUS_CHECKSUM_ERROR: "CHECKSUM_ERROR: Frame checksum validation failed.", # As reported by reader status
    STATUS_UNSUPPORTED_TLV_TYPE: "UNSUPPORTED_TLV_TYPE: Internal error - Unsupported TLV type encountered during processing.",
    STATUS_FLASH_ERROR: "FLASH_ERROR: Error writing parameters to flash memory.",
    STATUS_INTERNAL_ERROR: "INTERNAL_ERROR: Unspecified internal reader error.",
}