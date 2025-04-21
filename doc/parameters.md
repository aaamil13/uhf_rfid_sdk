# Parameters Guide

This guide explains how to work with the complex parameter structures used by some reader commands, such as `get_working_params` and `set_transport_params`.

These parameters are grouped into logical blocks (e.g., Working Parameters, Transport Parameters) and are represented by Python `dataclass` instances defined in `uhf_rfid.protocols.cph.parameters`.

## Using Parameter Dataclasses

When you call a getter function like `get_working_params()`, it returns an instance of the corresponding dataclass (e.g., `WorkingParams`) populated with the current values from the reader.

```python
# Example: Getting Working Parameters
working_params = await reader.get_working_params()
print(f"Current Antenna ID: {working_params.antenna_id}")
print(f"Current Read Power: {working_params.read_power}")
```

To modify parameters, you typically get the current settings, modify the desired fields on the dataclass instance, and then pass the modified instance back to the corresponding setter function.

```python
# Example: Modifying and Setting Working Parameters
working_params = await reader.get_working_params()

# Change antenna and power
working_params.antenna_id = 2
working_params.read_power = 25 # Set power to 25 dBm

# Apply the changes
await reader.set_working_params(working_params)
```

The library handles the packing and unpacking of these dataclasses into the byte formats required by the CPH protocol automatically.

## Parameter Definitions

Below are the definitions for the known complex parameter dataclasses. Note the warnings regarding the packing formats.

### `ExtParams`

Extended parameters, often related to reader identification and basic modes.

*   `reader_address` (`int`): Address of the reader.
*   `read_pause` (`int`): Pause time between reads (milliseconds).
*   `work_mode` (`int`): Reader work mode (e.g., `0` for answer mode).
*   `neighbour_judge_time` (`int`): Time threshold for judging neighboring readers (units unclear, likely ms or ticks).
*   `enable_relay` (`bool`): Whether the relay is enabled.
*   `relay_on_time` (`int`): Duration the relay stays on (units unclear, likely ms).
*   `baud_rate_index` (`int`): Index representing the serial baud rate.
*   `enable_buzzer` (`bool`): Whether the buzzer is enabled.

### `WorkingParams`

Parameters related to the core RFID reading process (antenna, power, frequency).

*   `antenna_id` (`int`): Currently active antenna ID.
*   `inventory_mode` (`int`): Inventory mode (e.g., `MODE_ANSWER` or `MODE_EPC_TID`).
*   `single_poll_interval` (`int`): Interval between polls in single inventory mode (ms).
*   `read_power` (`int`): Transmit power in dBm.
*   `frequency_region` (`int`): Index for the operating frequency region (e.g., China, US, EU).
*   `frequency_start` (`int`): Start frequency value (units depend on region, often kHz).
*   `frequency_end` (`int`): End frequency value (units depend on region, often kHz).
*   `rf_link_profile` (`int`): RF link profile index.
*   `filter_time` (`int`): Tag filtering time in milliseconds.

*   **`_PACK_FORMAT`**: `"!BBBHBBHHBH"` (14 bytes)

    **Warning**: The packing format for `WorkingParams` is based on inference and analysis of related code/documentation. While it appears correct for common fields, **verify its behavior carefully**, especially if using less common fields or different reader firmware versions.

### `TransportParams`

Parameters related to communication interfaces (Network, Serial).

*   `mode` (`int`): Transport mode (e.g., `0` for TCP Client, `1` for TCP Server).
*   `ip_address` (`str`): Reader's IP address.
*   `subnet_mask` (`str`): Subnet mask.
*   `gateway` (`str`): Gateway address.
*   `local_port` (`int`): Local port number (for TCP Server mode).
*   `remote_ip_address` (`str`): Remote IP address (for TCP Client mode).
*   `remote_port` (`int`): Remote port number (for TCP Client mode).
*   `mac_address` (`str`): Reader's MAC address (read-only).
*   `rs232_baud_rate_index` (`int`): Index for RS232 baud rate.
*   `rs485_baud_rate_index` (`int`): Index for RS485 baud rate.
*   `wiegand_protocol` (`int`): Wiegand protocol type.
*   `wiegand_pulse_width` (`int`): Wiegand pulse width (microseconds).
*   `wiegand_pulse_interval` (`int`): Wiegand pulse interval (microseconds).
*   `wiegand_data_interval` (`int`): Wiegand data interval (microseconds).

*   **`_PACK_FORMAT`**: `"!B 4s 4s 4s H 4s H 6s BB B H H H"` (38 bytes)

    **Warning**: Similar to `WorkingParams`, the packing format for `TransportParams` is **speculative**. IP/MAC addresses and ports seem standard, but **verify Wiegand and serial settings** if they are critical to your application.

### `AdvanceParams`

Advanced or less commonly used parameters.

*   `q_value` (`int`): EPC Gen2 Q value (0-15).
*   `session` (`int`): EPC Gen2 Session (0-3).
*   `inventory_target` (`int`): EPC Gen2 Inventory Target (A=0, B=1).
*   `inventory_flag` (`int`): Inventory flags (bitmask, meaning varies).
*   `scan_time` (`int`): Scan duration (units unclear, likely related to inventory cycles or ms).
*   `sleep_time` (`int`): Sleep duration between scans (ms).
*   `tag_upload_mode` (`int`): Mode for tag data upload (e.g., immediate, filtered).
*   `heartbeat_interval` (`int`): Interval for heartbeat signals (seconds).
*   `alarm_enable` (`bool`): Enable/disable alarm functionality (EAS/Sound/Light).
*   `eas_detection_method` (`int`): Method for EAS detection.
*   `tag_type_filter` (`int`): Filter based on tag type (e.g., EPC Gen2, 6B).
*   `trigger_mode` (`int`): Trigger mode (e.g., continuous, external trigger).
*   `trigger_delay` (`int`): Delay after trigger activation (ms).
*   `trigger_hold_time` (`int`): Duration to keep trigger active (ms).
*   `antenna_sequence` (`List[int]`): Sequence of antennas to use (up to 16).
*   `antenna_dwell_time` (`List[int]`): Dwell time for each antenna in the sequence (ms).

*   **`_PACK_FORMAT`**: `"!BBBBHHBBBBBBHH 16B 16H"` (72 bytes)

    **Critical Warning**: The packing format for `AdvanceParams` is **highly speculative** and based heavily on inference. The meaning and exact packing of many fields (especially flags, trigger settings, antenna sequences/dwell times) are uncertain without official documentation or extensive testing. **Use extreme caution when setting `AdvanceParams`. Incorrect values or packing could lead to unpredictable reader behavior or require a factory reset.** Thorough verification with your specific reader model is essential.

### Other Parameter Structures

The library also defines dataclasses for other parameter sets, generally used with specific commands:

*   `UsbDataParams`: Related to USB HID output format.
*   `DataFlagParams`: Flags controlling which data fields (RSSI, Antenna ID, Frequency) are included in tag reports.
*   `ModbusParams`: Configuration for Modbus communication.

Refer to the source code (`uhf_rfid/protocols/cph/parameters.py`) and the specific reader command documentation (`get_usb_data`, `set_data_flag`, etc.) for details on these.

## Important Considerations

*   **Speculative Formats**: As highlighted above, the byte packing formats (`_PACK_FORMAT`) for `WorkingParams`, `TransportParams`, and especially `AdvanceParams` are derived from reverse engineering or interpreting related code, not from official protocol specifications. They might be incorrect or incomplete for your reader model or firmware version.
*   **Verification**: Always verify the effect of setting complex parameters. Read the parameters back after setting them (`get_..._params()`) to confirm the values were accepted as expected. Test the reader's behavior thoroughly after changing these settings.
*   **Factory Reset**: Be prepared to perform a factory reset on the reader (using `set_default_params()` or a physical method if necessary) if incorrect advanced parameter settings cause issues.
*   **Reader Documentation**: Consult the manufacturer's documentation for your specific reader model, if available, for the most accurate parameter definitions and ranges. 