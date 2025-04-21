# uhf_rfid Python Library Documentation

Welcome to the documentation for the `uhf_rfid` Python library.

This library provides an asynchronous interface for interacting with UHF RFID readers that utilize the CPH communication protocol (versions similar to v4.0.1 / v4.0.3 as inferred from reference implementations).

**Repository:** [https://github.com/aaamil13/uhf_rfid_sdk](https://github.com/aaamil13/uhf_rfid_sdk)

## Key Features

*   **Asynchronous:** Built with `asyncio` for non-blocking I/O operations, suitable for integration into modern async Python applications.
*   **Transport Agnostic:** Supports different communication transports like Serial (RS232/USB-Serial) and TCP/IP (Client).
*   **Callback-based Notifications:** Allows registering specific asynchronous callbacks for different reader events like tag reads (online/offline), record uploads, and heartbeats.
*   **Comprehensive Command Set:** Implements a wide range of commands found in typical CPH-based readers, including inventory control, parameter management (simple and complex), tag memory operations (read/write/lock), RTC management, and device operations (relay/audio).
*   **Structured Parameter Handling:** Uses Python dataclasses (`ExtParams`, `WorkingParams`, etc.) for easier management of complex reader settings (where format is known or inferred).

## Important Notes

*   **Parameter Format Verification:** The exact byte-level format for some complex parameters (especially `AdvanceParams`, but also `WorkingParams` and `TransportParams`) and commands without clear TLV wrappers (like USB/DataFlag/Modbus settings) has been inferred from reference implementations. **It is crucial to verify these formats against the official documentation for your specific reader model or through testing to ensure correct operation.** See the [Parameters](parameters.md) page for details.
*   **Tag Selection:** The implemented protocol version does not appear to support selecting specific tags for operations like read/write/lock (e.g., via EPC mask). These operations will likely affect the first tag found by the reader.

## Getting Started

1.  **Installation:** See the [Installation Guide](installation.md).
2.  **Quickstart:** Check the [Quickstart Example](quickstart.md) for a basic usage scenario.
3.  **Examples:** Explore practical examples in the `doc/examples/` directory.

## Reference

*   **API Reference:** Detailed documentation for the `Reader` class and its methods can be found in the [API Reference](api_reference.md).
*   **Parameters:** Learn more about the complex parameter structures in [Parameters](parameters.md).
*   **Transport:** Information on configuring Serial or TCP transport in [Transport Configuration](transport.md).

## Troubleshooting

Refer to the [Troubleshooting Guide](troubleshooting.md) for common issues and solutions. 