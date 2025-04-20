# UHF RFID Communication Library

# uhf-rfid - Async UHF RFID Reader Library

Asynchronous library for communicating with UHF RFID readers, initially supporting the CPH Communication Protocol v4.0.1. Designed for flexibility and extension to other protocols and transport methods.

## Features

*   **Asynchronous:** Built on `asyncio` for non-blocking I/O, suitable for network and serial communication.
*   **Transport Layers:** Supports Serial (`pyserial-asyncio`) and TCP communication. Mock transport for testing.
*   **Protocol Abstraction:** Base classes allow adding support for different reader protocols. Includes implementation for CPH v4.0.1.
*   **Callback System:** Register async callbacks for notifications (e.g., tag reads).
*   **Graceful Handling:** Includes connection management, status tracking, and specific exceptions.
*   **Type Hinted:** Fully type-hinted for better development experience and static analysis.

## Installation

You can install the library directly from source using pip:

```bash
pip install .
# For development (including test dependencies):
pip install -e ".[dev]"
```

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