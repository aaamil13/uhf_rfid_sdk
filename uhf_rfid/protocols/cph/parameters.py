"""
Data classes representing complex parameter structures for the CPH protocol.
"""

from dataclasses import dataclass
import struct

@dataclass
class ExtParams:
    """Represents the Extended Parameters (TLV 0x29)."""
    relay_mode: int = 0     # 0: Auto, 1: Manual
    relay_time: int = 0     # Seconds (0-255)
    verify_flag: int = 0    # 0: Disable, 1: Enable tag verification
    verify_pwd: int = 0      # 16-bit verification password

    def encode(self) -> bytes:
        """Encodes the extended parameters into bytes for the TLV value."""
        # Format: RelayMode(1) RelayTime(1) VerifyFlag(1) VerifyPwd(2)
        if not (0 <= self.relay_mode <= 1):
            raise ValueError("Relay Mode must be 0 or 1")
        if not (0 <= self.relay_time <= 255):
            raise ValueError("Relay Time must be between 0 and 255")
        if not (0 <= self.verify_flag <= 1):
            raise ValueError("Verify Flag must be 0 or 1")
        if not (0 <= self.verify_pwd <= 0xFFFF):
            raise ValueError("Verify Password must be between 0 and 65535")

        return struct.pack(">BBBH", 
                           self.relay_mode, 
                           self.relay_time, 
                           self.verify_flag, 
                           self.verify_pwd)

    @classmethod
    def decode(cls, data: bytes) -> "ExtParams":
        """Decodes bytes (from TLV value) into an ExtParams object."""
        if len(data) != 5:
            raise ValueError(f"Expected 5 bytes for ExtParams, got {len(data)}")
        
        relay_mode, relay_time, verify_flag, verify_pwd = struct.unpack(">BBBH", data)
        return cls(relay_mode=relay_mode, 
                   relay_time=relay_time, 
                   verify_flag=verify_flag, 
                   verify_pwd=verify_pwd)

@dataclass
class WorkingParams:
    """Represents the Working Parameters (TLV 0x23)."""
    # Based on C# RfidWorkParam structure and typical settings
    read_duration: int = 300  # Inventory duration (e.g., ms or 10ms units? Assume ms for now) - Need to confirm unit
    read_interval: int = 50   # Interval between inventory rounds (ms?)
    work_mode: int = 0        # 0: Answer mode, 1: Active mode, 2: Trigger mode
    tag_upload_flag: int = 0  # Bitmask for data to upload (EPC, TID, User, RSSI, etc.)
    trigger_mode_output: int = 0 # 0: Relay OFF after read, 1: Relay ON after read
    wiegand_protocol: int = 0 # 0: Wiegand 26, 1: Wiegand 34
    wiegand_interval: int = 0 # Interval for Wiegand output (ms?)
    wiegand_pulse_width: int = 0 # Wiegand pulse width (us?)
    wiegand_pulse_interval: int = 0 # Wiegand pulse interval (us?)
    iso_area: int = 0         # ISO 18000-6B area (0-7?)
    iso_addr: int = 0         # ISO 18000-6B address (0-255)
    iso_word_count: int = 0   # ISO 18000-6B word count (0-?)

    # Define the pack format string based on expected sizes
    # Check C# sizes: uc(1), uc(1), uc(1), us(2), uc(1), uc(1), us(2), us(2), us(2), uc(1), uc(1), uc(1)
    # Assuming H=ushort, B=uc
    # read_duration(H), read_interval(H), work_mode(B), tag_upload_flag(H), trigger_mode_output(B), wiegand_protocol(B),
    # wiegand_interval(H), wiegand_pulse_width(H), wiegand_pulse_interval(H), iso_area(B), iso_addr(B), iso_word_count(B)
    # Total: 2+2+1+2+1+1+2+2+2+1+1+1 = 18 bytes
    _PACK_FORMAT = ">HHBHBBHHHBBB"
    _EXPECTED_LEN = struct.calcsize(_PACK_FORMAT)

    def encode(self) -> bytes:
        """Encodes the working parameters into bytes."""
        # Add validation for each field based on expected ranges
        if not (0 <= self.work_mode <= 2):
            raise ValueError("Work Mode must be 0, 1, or 2")
        # ... add more validation for other fields ...

        try:
            return struct.pack(
                self._PACK_FORMAT,
                self.read_duration,
                self.read_interval,
                self.work_mode,
                self.tag_upload_flag,
                self.trigger_mode_output,
                self.wiegand_protocol,
                self.wiegand_interval,
                self.wiegand_pulse_width,
                self.wiegand_pulse_interval,
                self.iso_area,
                self.iso_addr,
                self.iso_word_count
            )
        except struct.error as e:
            raise ValueError(f"Error packing WorkingParams: {e}") from e

    @classmethod
    def decode(cls, data: bytes) -> "WorkingParams":
        """Decodes bytes into a WorkingParams object."""
        if len(data) != cls._EXPECTED_LEN:
            raise ValueError(f"Expected {cls._EXPECTED_LEN} bytes for WorkingParams, got {len(data)}")
        
        try:
            unpacked_data = struct.unpack(cls._PACK_FORMAT, data)
            return cls(*unpacked_data)
        except struct.error as e:
            raise ValueError(f"Error unpacking WorkingParams: {e}") from e

@dataclass
class TransportParams:
    """Represents the Transport Parameters (TLV 0x24)."""
    # Based on C# RfidTransmissionParam structure
    transport_type: int = 0 # 0: RS232/UART, 1: RS485, 2: RJ45(TCP Server), 3: RJ45(TCP Client), 4: WIFI(TCP Server), 5: WIFI(TCP Client)
    uart_baud_rate: int = 115200 # e.g., 9600, 19200, ..., 115200
    net_dhcp_flag: int = 0  # 0: Static IP, 1: DHCP
    net_ip_addr: str = "192.168.1.178" # Static IP address
    net_subnet_mask: str = "255.255.255.0" # Subnet mask
    net_gateway: str = "192.168.1.1"   # Gateway address
    net_local_port: int = 6000 # TCP Server/Local Port
    net_remote_ip_addr: str = "192.168.1.100" # TCP Client Remote IP
    net_remote_port: int = 6001 # TCP Client Remote Port
    heartbeat_interval: int = 0 # Heartbeat packet interval (seconds? 0=disable)

    # Packing needs careful consideration due to IP address strings.
    # C# likely packs them as 4 bytes each.
    _PACK_FORMAT_PREFIX = ">BII" # transport_type, uart_baud_rate, net_dhcp_flag (1+4+4 = 9 bytes)
    _IP_PACK_FORMAT = "BBBB" # 4 bytes for IP
    _PACK_FORMAT_SUFFIX = ">HHB" # net_local_port, net_remote_port, heartbeat_interval (2+2+1 = 5 bytes)
    # Total expected: 9 + 4*3 + 5 = 26 bytes?

    @staticmethod
    def _ip_to_bytes(ip_str: str) -> bytes:
        parts = ip_str.split('.')
        if len(parts) != 4:
            raise ValueError(f"Invalid IPv4 address format: {ip_str}")
        try:
            return bytes(int(p) for p in parts)
        except ValueError:
            raise ValueError(f"Invalid byte value in IP address: {ip_str}")

    @staticmethod
    def _bytes_to_ip(ip_bytes: bytes) -> str:
        if len(ip_bytes) != 4:
             raise ValueError("IP address must be 4 bytes long")
        return ".".join(str(b) for b in ip_bytes)

    def encode(self) -> bytes:
        """Encodes the transport parameters into bytes."""
        # Add validation...
        try:
            ip_bytes = self._ip_to_bytes(self.net_ip_addr)
            mask_bytes = self._ip_to_bytes(self.net_subnet_mask)
            gw_bytes = self._ip_to_bytes(self.net_gateway)
            remote_ip_bytes = self._ip_to_bytes(self.net_remote_ip_addr)

            prefix = struct.pack(self._PACK_FORMAT_PREFIX, 
                                 self.transport_type, 
                                 self.uart_baud_rate, 
                                 self.net_dhcp_flag)
            suffix = struct.pack(self._PACK_FORMAT_SUFFIX,
                                 self.net_local_port,
                                 self.net_remote_port,
                                 self.heartbeat_interval)
            # Combine all parts
            return prefix + ip_bytes + mask_bytes + gw_bytes + remote_ip_bytes + suffix
        except (struct.error, ValueError) as e:
            raise ValueError(f"Error packing TransportParams: {e}") from e

    @classmethod
    def decode(cls, data: bytes) -> "TransportParams":
        """Decodes bytes into a TransportParams object."""
        # Calculate expected length based on format parts
        expected_len = struct.calcsize(cls._PACK_FORMAT_PREFIX) + 4 * 4 + struct.calcsize(cls._PACK_FORMAT_SUFFIX)
        if len(data) != expected_len:
             raise ValueError(f"Expected {expected_len} bytes for TransportParams, got {len(data)}")

        try:
            pfx_len = struct.calcsize(cls._PACK_FORMAT_PREFIX)
            sfx_start = pfx_len + 4 * 4
            sfx_len = struct.calcsize(cls._PACK_FORMAT_SUFFIX)

            prefix_data = data[:pfx_len]
            ip_data = data[pfx_len : pfx_len + 4]
            mask_data = data[pfx_len + 4 : pfx_len + 8]
            gw_data = data[pfx_len + 8 : pfx_len + 12]
            remote_ip_data = data[pfx_len + 12 : sfx_start]
            suffix_data = data[sfx_start:]

            transport_type, uart_baud_rate, net_dhcp_flag = struct.unpack(cls._PACK_FORMAT_PREFIX, prefix_data)
            net_local_port, net_remote_port, heartbeat_interval = struct.unpack(cls._PACK_FORMAT_SUFFIX, suffix_data)

            return cls(
                transport_type=transport_type,
                uart_baud_rate=uart_baud_rate,
                net_dhcp_flag=net_dhcp_flag,
                net_ip_addr=cls._bytes_to_ip(ip_data),
                net_subnet_mask=cls._bytes_to_ip(mask_data),
                net_gateway=cls._bytes_to_ip(gw_data),
                net_local_port=net_local_port,
                net_remote_ip_addr=cls._bytes_to_ip(remote_ip_data),
                net_remote_port=net_remote_port,
                heartbeat_interval=heartbeat_interval
            )
        except (struct.error, ValueError) as e:
             raise ValueError(f"Error unpacking TransportParams: {e}") from e

@dataclass
class AdvanceParams:
    """Represents the Advance Parameters (TLV 0x25)."""
    # Based on C# RfidAdvanceParam structure - Needs careful checking!
    rf_link_profile: int = 0  # RF Link Profile (e.g., 0:DSB_ASK_FM0_M2, 1:PR_ASK_TARI625_M4, etc.)
    rf_region: int = 0        # RF Region (e.g., 0: China2, 1: US, 2: Europe, 3: China1, ...)
    rf_spectrum_start: int = 0 # Start Frequency (kHz or index? Assume kHz)
    rf_spectrum_end: int = 0   # End Frequency (kHz or index? Assume kHz)
    rf_inventory_ant_flag: int = 0 # Bitmask for antennas used in inventory
    rf_inventory_session: int = 0 # Inventory Session (0-3)
    rf_inventory_target: int = 0 # Inventory Target (A=0, B=1)
    rf_fm0_div: int = 0      # FM0 divisor?
    rf_miller_type: int = 0  # Miller Type (e.g., 2, 4, 8)
    rf_filter_coefficient: int = 0 # Filter coefficient?
    rf_tari: int = 0         # Tari value (e.g., 0=25us, 1=12.5us, 2=6.25us)
    rf_write_power: int = 30 # Write power (dBm)
    rf_carrier_flag: int = 0 # Carrier flag (0 or 1?)

    # Define the pack format string - Highly speculative based on C# names!
    # uc(1)*7 + us(2)*2 + uc(1)*3 ? => BBBBBBB HH BBB = 16 bytes? NEEDS VERIFICATION
    _PACK_FORMAT = ">BBIIIBB BBBBH B"
    _EXPECTED_LEN = struct.calcsize(_PACK_FORMAT)

    def encode(self) -> bytes:
        """Encodes the advance parameters into bytes."""
        # Add extensive validation based on actual allowed ranges per field!
        if not (0 <= self.rf_link_profile <= 5): # Guessing range
            raise ValueError(f"Invalid RF Link Profile: {self.rf_link_profile}")
        # ... add more validation ...
        
        try:
            return struct.pack(
                self._PACK_FORMAT,
                self.rf_link_profile,
                self.rf_region,
                self.rf_spectrum_start,
                self.rf_spectrum_end,
                self.rf_inventory_ant_flag,
                self.rf_inventory_session,
                self.rf_inventory_target,
                self.rf_fm0_div,
                self.rf_miller_type,
                self.rf_filter_coefficient,
                self.rf_tari,
                self.rf_write_power,
                self.rf_carrier_flag
            )
        except struct.error as e:
            raise ValueError(f"Error packing AdvanceParams: {e}") from e

    @classmethod
    def decode(cls, data: bytes) -> "AdvanceParams":
        """Decodes bytes into an AdvanceParams object."""
        if len(data) != cls._EXPECTED_LEN:
            raise ValueError(f"Expected {cls._EXPECTED_LEN} bytes for AdvanceParams, got {len(data)}")
        
        try:
            unpacked_data = struct.unpack(cls._PACK_FORMAT, data)
            return cls(*unpacked_data)
        except struct.error as e:
            raise ValueError(f"Error unpacking AdvanceParams: {e}") from e

# Add other parameter classes here later (WorkingParams, TransportParams, AdvanceParams)
# ... 

# --- Other Parameter Structures (Often used raw in commands) ---

@dataclass
class UsbDataParams:
    """Represents USB HID related parameters (Speculative)."""
    usb_enable: int = 0 # 0: Disable, 1: Enable
    data_interval: int = 0 # Interval (units unclear, maybe 10ms?)
    keyboard_layout: int = 0 # Keyboard layout code (e.g., 0=US, 2=DE)

    _PACK_FORMAT = ">BBB"
    _EXPECTED_LEN = struct.calcsize(_PACK_FORMAT)

    def encode(self) -> bytes:
        try:
            return struct.pack(self._PACK_FORMAT, self.usb_enable, self.data_interval, self.keyboard_layout)
        except struct.error as e:
            raise ValueError(f"Error packing UsbDataParams: {e}") from e

    @classmethod
    def decode(cls, data: bytes) -> "UsbDataParams":
        if len(data) != cls._EXPECTED_LEN:
             raise ValueError(f"Expected {cls._EXPECTED_LEN} bytes for UsbDataParams, got {len(data)}")
        try:
            return cls(*struct.unpack(cls._PACK_FORMAT, data))
        except struct.error as e:
            raise ValueError(f"Error unpacking UsbDataParams: {e}") from e

@dataclass
class DataFlagParams:
    """Represents data format flags (Speculative)."""
    data_flag: int = 0 # Bitmask (e.g., 0x01=EPC, 0x02=TID, 0x04=RSSI, 0x08=AntNo)
    data_format: int = 0 # 0: Hex, 1: Decimal

    _PACK_FORMAT = ">HB"
    _EXPECTED_LEN = struct.calcsize(_PACK_FORMAT)

    def encode(self) -> bytes:
        try:
            return struct.pack(self._PACK_FORMAT, self.data_flag, self.data_format)
        except struct.error as e:
            raise ValueError(f"Error packing DataFlagParams: {e}") from e

    @classmethod
    def decode(cls, data: bytes) -> "DataFlagParams":
        if len(data) != cls._EXPECTED_LEN:
             raise ValueError(f"Expected {cls._EXPECTED_LEN} bytes for DataFlagParams, got {len(data)}")
        try:
            return cls(*struct.unpack(cls._PACK_FORMAT, data))
        except struct.error as e:
            raise ValueError(f"Error unpacking DataFlagParams: {e}") from e

@dataclass
class ModbusParams:
    """Represents Modbus parameters (Placeholder/Speculative)."""
    # Structure unknown - add fields based on documentation or C# code if available
    modbus_address: int = 1
    modbus_baud_rate: int = 9600
    # ... other fields ...

    # Placeholder format - MUST BE VERIFIED
    _PACK_FORMAT = ">BI"
    _EXPECTED_LEN = struct.calcsize(_PACK_FORMAT)

    def encode(self) -> bytes:
        # Placeholder implementation
        logger.warning("Encoding ModbusParams using speculative format.")
        try:
            # Replace with actual packing based on known structure
            return struct.pack(self._PACK_FORMAT, self.modbus_address, self.modbus_baud_rate)
        except struct.error as e:
            raise ValueError(f"Error packing ModbusParams: {e}") from e

    @classmethod
    def decode(cls, data: bytes) -> "ModbusParams":
        # Placeholder implementation
        logger.warning("Decoding ModbusParams using speculative format.")
        if len(data) != cls._EXPECTED_LEN:
            raise ValueError(f"Expected {cls._EXPECTED_LEN} bytes for ModbusParams, got {len(data)}")
        try:
             # Replace with actual unpacking
             addr, baud = struct.unpack(cls._PACK_FORMAT, data)
             return cls(modbus_address=addr, modbus_baud_rate=baud)
        except struct.error as e:
             raise ValueError(f"Error unpacking ModbusParams: {e}") from e 