# UHF RFID Library (`uhf-rfid`)

[![PyPI version](https://badge.fury.io/py/uhf-rfid.svg)](https://badge.fury.io/py/uhf-rfid) <!-- Placeholder - update if/when published -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Asynchronous Python library for interacting with UHF RFID readers, initially focusing on the CPH protocol (v4.0.1).

## Features

*   **Asynchronous:** Built with `asyncio` for non-blocking communication.
*   **Modular Design:** Separates transport (Serial, TCP, Mock) and protocol layers.
*   **High-Level API:** Simple `Reader` class for common tasks:
    *   Connecting/disconnecting.
    *   Getting device information (version).
    *   Managing reader parameters (power, buzzer, working modes, transport settings, etc.).
    *   Starting/stopping inventory scans (continuous and single burst).
    *   Handling tag notifications via asynchronous callbacks.
    *   Reading and writing tag memory banks (EPC, User, TID, Reserved).
    *   Locking tag memory areas.
    *   **Killing (permanently disabling) tags (use with extreme caution!).**
    *   Controlling reader RTC (Real-Time Clock).
    *   Operating reader relay and audio features (if supported).
*   **Protocol Implementation:** Includes specific implementation for CPH v4.0.1.
*   **Utility Functions:**
    *   Serial port scanner to detect available ports (`uhf_rfid.utils.serial_scanner`).
    *   **Tag identification utility based on TID and JSON definitions (`uhf_rfid.utils.tag_utils`).**
*   **Clear Exceptions:** Defines specific error types for better handling.

## Installation

```bash
pip install uhf-rfid
```

Or for development (to include testing dependencies and use local changes immediately):

```bash
# Clone the repository
git clone https://github.com/aaamil13/uhf_rfid_sdk.git
cd uhf_rfid_sdk

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

```python
import asyncio
import logging
from uhf_rfid import Reader, SerialTransport, CPHProtocol, TagReadData

logging.basicConfig(level=logging.INFO)

async def tag_handler(tag: TagReadData):
    print(f"TAG SEEN: EPC={tag.epc} RSSI={tag.rssi}")

async def main():
    # Adjust port as needed
    transport = SerialTransport(port='COM3') # Or '/dev/ttyUSB0' on Linux
    protocol = CPHProtocol()

    try:
        async with Reader(transport=transport, protocol=protocol) as reader:
            print("Reader connected. Registering callback...")
            await reader.register_tag_notify_callback(tag_handler)

            print("Starting inventory for 5 seconds...")
            await reader.start_inventory()
            await asyncio.sleep(5)
            await reader.stop_inventory()
            print("Inventory stopped.")

            await reader.unregister_tag_notify_callback(tag_handler)
            print("Callback unregistered.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

See the `doc/examples/` and `examples/` directories for more detailed usage examples covering various commands.

## Tag Identification Utility

The library includes a utility function `uhf_rfid.utils.identify_tag(reader, epc)` that attempts to identify the manufacturer and model of a tag based on its TID (Tag Identifier) memory bank.

1.  **Reads TID:** Reads the first few bytes of the tag's TID memory.
2.  **Parses:** Extracts the Manufacturer ID (MDID) and Tag Model Number (TMN) according to the EPC Gen2 standard.
3.  **Looks up Definitions:** Searches for the MDID and TMN in a JSON file (`uhf_rfid/utils/tag_definitions.json`).

**Return Value:**

The function returns a dictionary containing:
*   `epc`: The EPC of the tag.
*   `tid_raw`: The raw hex string of the TID data read.
*   `manufacturer_id`: The parsed MDID.
*   `tag_model_number`: The parsed TMN.
*   `tag_info`: A dictionary containing detailed information found in the JSON file (model name, memory sizes, features, notes), or `None` if no definition was found.
*   `error`: A string describing any error that occurred during reading or parsing, or `None` on success.

**`tag_definitions.json` Structure:**

This file contains known tag definitions. You can extend this file with definitions for tags you commonly encounter.

```json
{
  "manufacturers": {
    "<MDID_as_string>": {
      "name": "Manufacturer Name",
      "models": {
        "<TMN_as_string>": {
          "model_name": "Tag Model Name",
          "memory": {
            "epc_bits": <number>,
            "user_bits": <number>,
            "tid_bits": <number>,
            "reserved_access_bits": <number>,
            "reserved_kill_bits": <number>
          },
          "features": ["Feature1", "Feature2"],
          "notes": "Optional notes about the tag."
        }
        // ... other models from this manufacturer
      }
    }
    // ... other manufacturers
  }
}
```

See `examples/identify_tag_example.py` for usage.

## Dependencies

*   Python >= 3.8
*   `pyserial-asyncio >= 0.6` (for serial communication)

## Third-Party Licenses

This project relies on the following core dependencies:

*   **pyserial-asyncio:** Licensed under the BSD 3-Clause License. (Copyright © 2015-2021 pySerial-team)
*   **pyserial:** Licensed under the BSD 3-Clause License. (Copyright © 2001-2020 Chris Liechti)

The BSD 3-Clause license is compatible with the MIT license used for this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note:** Remember to replace `[Your Name/Organization]` in the `LICENSE` file with the actual copyright holder information.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
(Consider adding more detailed contribution guidelines if applicable).

## TODO / Future Enhancements

*   Add more comprehensive tests to increase code coverage.
*   Generate API documentation (e.g., using Sphinx).
*   Implement support for other RFID protocols or reader types.
*   Refine parameter dataclasses and validation.
*   Add specific tests for `kill_tag` (requires careful mocking or dedicated test tags).
*   Add tests for `serial_scanner`.

## What's New in v0.2.0

*   **Refactoring:** Major internal refactoring of the `Reader` class. Most command methods (`set_power`, `get_power`, `read_tag`, `write_tag`, `lock_tag`, inventory methods, parameter getters/setters, etc.) now use a unified `_execute_command` helper. This improves consistency and maintainability.
*   **Protocol Layer Delegation:** Command encoding and response decoding logic is now more clearly delegated to the protocol layer implementation (`CPHProtocol` in this case), making the `Reader` class more protocol-agnostic.
*   **Improved Error Handling:** Enhanced error handling within the `_execute_command` helper and refined exception classes (`CommandError` now handles encoding/decoding errors better).
*   **Bug Fixes:** Corrected several import errors and inconsistencies found during testing. Fixed issues in test setup and assertions related to mocking and argument passing.
*   **Test Suite:** Expanded and corrected the test suite (`tests/core/test_reader.py`) to cover the refactored methods and improve reliability.

## Migration from v0.1.0

*   **`kill_tag` Method:** The `reader.kill_tag()` method is temporarily **removed/commented out** in v0.2.0. The CPH protocol implements the kill operation as part of the Lock command (`CMD_LOCK_TAG` with `OP_TYPE_KILL`), which requires further refactoring in both the `Reader` and `CPHProtocol` layers. This functionality will be restored in a future version. If you were using `kill_tag`, you will need to adapt your code once the refactored version is available or use lower-level commands if necessary.
*   **`ProtocolError` (`frame_part`):** The `frame_part` argument has been removed from several `ProtocolError` instantiations within the library, particularly where the error originated from TLV parsing or parameter validation rather than frame-level parsing. If your error handling specifically relied on accessing `error.frame_part` for these types of `ProtocolError`, you may need to adjust your logic. `CommandError` raised by the reader (due to status codes) may still contain the relevant frame in its `frame` attribute.
*   **Internal Changes:** While the public API of most `Reader` methods remains the same (arguments and return types), the internal implementation has changed significantly. This shouldn't affect standard usage but is worth noting.

## Basic Usage

```bash
pip install .
pip install -e ".[dev]"