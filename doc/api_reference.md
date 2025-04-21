# API Reference - `uhf_rfid.core.reader.Reader`

This document provides a reference for the core `Reader` class, which is the main interface for interacting with the UHF RFID reader.

## Initialization

### `Reader(transport, protocol, response_timeout=5.0, logger=None)`

Initializes the `Reader` instance.

*   **`transport`**: An instance of a transport layer class (e.g., `SerialTransport`, `TcpTransport`). Responsible for the physical communication with the reader.
*   **`protocol`**: An instance of a protocol layer class (e.g., `CPHProtocol`). Responsible for framing, parsing, and generating commands according to the reader's specific protocol.
*   **`response_timeout`** (`float`, optional): The maximum time in seconds to wait for a response from the reader after sending a command. Defaults to `5.0`.
*   **`logger`** (`logging.Logger`, optional): A logger instance for internal logging. If `None`, a default logger named `uhf_rfid.Reader` is created.

## Connection Management

### `async connect()`

Establishes a connection to the reader using the configured transport layer. Raises `ConnectionError` if the connection fails.

### `async disconnect()`

Closes the connection to the reader.

### `is_connected` -> `bool`

A property that returns `True` if the reader is currently connected, `False` otherwise.

### `status` -> `ConnectionStatus`

A property that returns the current connection status (enum `ConnectionStatus`: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `DISCONNECTING`).

### `set_status_change_callback(callback: Callable[[ConnectionStatus], None])`

Registers a callback function that will be invoked whenever the `ConnectionStatus` changes. The callback receives the new status as its only argument.

### Async Context Manager (`async with reader: ...`)

The `Reader` class supports asynchronous context management. Using `async with reader:` will automatically call `connect()` upon entering the block and `disconnect()` upon exiting the block (even if errors occur).

## Notification Callbacks

These methods allow you to register functions that will be called when the reader sends asynchronous notifications (like tag reads or heartbeats).

### `async register_tag_notify_callback(callback: Callable)`
### `async register_record_notify_callback(callback: Callable)`
### `async register_heartbeat_callback(callback: Callable)`

Registers a callback function for a specific type of notification (tag uploads, record uploads, heartbeats). The callback function should accept the following arguments:

*   `frame_type` (`int`): The type of the frame (e.g., CPH `COMMAND` or `NOTIFICATION`).
*   `address` (`int`): The reader address (usually `0xFFFF` for CPH).
*   `frame_code` (`int`): The specific command or notification code (e.g., CPH `NOTIF_TAG_UPLOADED`).
*   `params` (`Any`): The parsed parameters associated with the notification. The structure depends on the specific notification type and the protocol implementation.

### `async unregister_callback(callback: Callable)`

Unregisters a previously registered callback function.

## Reader Commands

These methods send commands to the reader and typically wait for a response. They often raise `CommandError` if the reader responds with an error status, or `TimeoutError` if no response is received within the configured timeout.

### `async get_version()` -> `str`

Retrieves the firmware version string from the reader.

### `async start_inventory(mode: int = 0)`

Starts the tag inventory process on the reader.

*   **`mode`** (`int`, optional): Inventory mode (protocol-specific, e.g., CPH `MODE_ANSWER` (0) or `MODE_EPC_TID` (2)). Defaults to `0`.

Tag data will be sent asynchronously via the registered tag notification callback.

### `async stop_inventory()`

Stops the ongoing tag inventory process.

### `async inventory_single_burst()` -> `dict`

Performs a single burst inventory and returns the first tag found (if any).
*   **Return Value**: A dictionary containing the tag data, typically including EPC, TID, RSSI, etc., depending on the protocol and reader configuration. Returns an empty dictionary if no tag is found immediately.

### `async reboot_reader()`

Sends a command to reboot the reader.

### `async set_parameter(param_type: int, value: Any)`

Sets a specific reader parameter.

*   **`param_type`** (`int`): The code identifying the parameter to set (protocol-specific, e.g., CPH `PARA_RELAY_CONTROL`).
*   **`value`** (`Any`): The value to set the parameter to. The type depends on the specific parameter.

### `async query_parameter(param_type: int)` -> `Any`

Queries the current value of a specific reader parameter.

*   **`param_type`** (`int`): The code identifying the parameter to query (protocol-specific).
*   **Return Value**: The current value of the parameter. The type depends on the specific parameter.

### `async set_power(power_dbm: int)`

Sets the reader's transmit power.

*   **`power_dbm`** (`int`): Power level in dBm (e.g., 10-30).

### `async get_power()` -> `int`

Gets the reader's current transmit power in dBm.

### `async set_buzzer(enable: bool)`

Enables or disables the reader's buzzer.

*   **`enable`** (`bool`): `True` to enable the buzzer, `False` to disable it.

### `async get_buzzer_status()` -> `bool`

Gets the current status of the reader's buzzer (`True` if enabled, `False` if disabled).

### `async set_filter_time(filter_time_ms: int)`

Sets the tag filtering time (duration a tag is ignored after being read).

*   **`filter_time_ms`** (`int`): Filter time in milliseconds.

### `async get_filter_time()` -> `int`

Gets the current tag filtering time in milliseconds.

### `async read_tag_memory(bank: int, start_addr: int, length: int, access_pwd: bytes = b'\x00\x00\x00\x00')` -> `bytes`

Reads data from a specific memory bank of a tag.

*   **`bank`** (`int`): Memory bank to read (e.g., `BANK_RESERVED`, `BANK_EPC`, `BANK_TID`, `BANK_USER`).
*   **`start_addr`** (`int`): Starting word address (1 word = 2 bytes).
*   **`length`** (`int`): Number of words to read.
*   **`access_pwd`** (`bytes`, optional): 4-byte access password if required. Defaults to `b'\x00\x00\x00\x00'`.
*   **Return Value**: The data read from the tag memory as bytes.

*Note*: Tag selection for this operation is often implicit (usually the last tag read or the only tag in the field). Behavior might vary between reader models.

### `async write_tag_memory(bank: int, start_addr: int, data: bytes, access_pwd: bytes = b'\x00\x00\x00\x00')`

Writes data to a specific memory bank of a tag.

*   **`bank`** (`int`): Memory bank to write to.
*   **`start_addr`** (`int`): Starting word address.
*   **`data`** (`bytes`): The data to write. Length must be an even number of bytes (multiple of words).
*   **`access_pwd`** (`bytes`, optional): 4-byte access password if required.

*Note*: Tag selection is typically implicit. Ensure data length is appropriate (word-aligned).

### `async set_default_params()`

Resets the reader parameters to their factory default values.

### `async get_rtc_time()` -> `datetime`

Gets the current time from the reader's Real-Time Clock (RTC).

*   **Return Value**: A `datetime` object representing the reader's time.

### `async set_rtc_time(dt: datetime)`

Sets the time on the reader's Real-Time Clock (RTC).

*   **`dt`** (`datetime`): The `datetime` object to set the reader's clock to.

### Complex Parameter Commands

These commands handle structured parameter blocks. See the [Parameters Guide](parameters.md) for details on the associated dataclasses.

*   **`async get_ext_params()` -> `ExtParams`**: Gets extended reader parameters.
*   **`async set_ext_params(params: ExtParams)`**: Sets extended reader parameters.
*   **`async get_working_params()` -> `WorkingParams`**: Gets working parameters (antenna, frequency, etc.).
*   **`async set_working_params(params: WorkingParams)`**: Sets working parameters.
*   **`async get_transport_params()` -> `TransportParams`**: Gets transport-related parameters (network settings, serial config).
*   **`async set_transport_params(params: TransportParams)`**: Sets transport-related parameters.
*   **`async get_advance_params()` -> `AdvanceParams`**: Gets advanced reader parameters.
*   **`async set_advance_params(params: AdvanceParams)`**: Sets advanced reader parameters.
*   **`async get_usb_data()` -> `UsbDataParams`**: Gets USB HID related parameters.
*   **`async set_usb_data(params: UsbDataParams)`**: Sets USB HID related parameters.
*   **`async get_data_flag()` -> `DataFlagParams`**: Gets data format flags.
*   **`async set_data_flag(params: DataFlagParams)`**: Sets data format flags.
*   **`async get_modbus_params()` -> `ModbusParams`**: Gets Modbus parameters.
*   **`async set_modbus_params(params: ModbusParams)`**: Sets Modbus parameters.

*Warning*: The exact structure and packing format for `WorkingParams`, `TransportParams`, and especially `AdvanceParams` might be speculative and require verification based on the specific reader model and firmware. See the [Parameters Guide](parameters.md).

### Other Commands

*   **`async relay_operation(relay_num: int, action: int)`**: Controls the reader's relays (if available).
    *   `relay_num` (`int`): Relay number (e.g., 1 or 2).
    *   `action` (`int`): Action code (e.g., CPH `RELAY_OFF`, `RELAY_ON`).
*   **`async play_audio(sound_type: int, repeat_count: int)`**: Plays a sound on the reader (if supported).
    *   `sound_type` (`int`): Type of sound (protocol-specific).
    *   `repeat_count` (`int`): Number of times to repeat the sound.
*   **`async set_record_upload_status(enable: bool)`**: Enables or disables the automatic upload of stored records (offline reads).
*   **`async lock_tag(lock_type: int, bank: int, access_pwd: bytes = b'\x00\x00\x00\x00')`**: Locks a memory bank of a tag.
    *   `lock_type` (`int`): Type of lock (protocol-specific).
    *   `bank` (`int`): Memory bank to lock.
    *   `access_pwd` (`bytes`): Access password.
*   **`async write_epc(epc_data: bytes, access_pwd: bytes = b'\x00\x00\x00\x00')`**: Writes a new EPC to a tag.
    *   `epc_data` (`bytes`): The new EPC data (length should be appropriate, e.g., 12 bytes for 96-bit EPC).
    *   `access_pwd` (`bytes`): Access password.
*   **`async verify_tag(data_to_verify: bytes, start_addr: int = 2, bank: int = 1)`**: Verifies data written to a tag memory bank.
    * `data_to_verify` (`bytes`): Data to match against tag memory.
    * `start_addr` (`int`): Starting word address in the bank (defaults to 2, the typical start of EPC).
    * `bank` (`int`): Memory bank to verify (defaults to 1, the EPC bank).

### Unimplemented / Unclear Commands

*   **`async prepare_firmware_update()`**: Intended to prepare the reader for a firmware update. *Implementation status unclear/incomplete.*
*   **`async write_wiegand_number(number: int)`**: Intended to write a Wiegand number (often used for access control). *Implementation status unclear/incomplete.*

## Exceptions

The `Reader` methods can raise various exceptions derived from `UhfRfidError`:

*   **`ConnectionError`**: Issues with the transport layer connection.
*   **`TimeoutError`**: No response received from the reader within the timeout period.
*   **`CommandError`**: The reader responded with an error status code for a command. Contains `status_code` and `get_status_message()`.
*   **`ProtocolError`**: Errors related to protocol framing or parsing (e.g., `FrameParseError`, `ChecksumError`).
*   **`ValueError`**: Invalid arguments provided to methods (e.g., incorrect data length for `write_tag_memory`). 