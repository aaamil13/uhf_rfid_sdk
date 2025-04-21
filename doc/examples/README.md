# UHF RFID Library Examples

This directory contains example scripts demonstrating how to use the `uhf-rfid` library from https://github.com/aaamil13/uhf_rfid_sdk.

## About the Library

The `uhf-rfid` library provides an asynchronous interface for communicating with UHF RFID readers. Its main goals are:

*   **Asynchronous Operations:** Leverages Python's `asyncio` for non-blocking communication, making it suitable for applications requiring responsiveness (like GUIs or network servers).
*   **Modularity:** Separates transport layers (Serial, TCP, Mock) from protocol implementations (currently CPH v4.0.1), allowing for easier extension and testing.
*   **Ease of Use:** Offers a high-level `Reader` class that simplifies common RFID operations like inventory, reading/writing tags, and configuring parameters.
*   **Clear Error Handling:** Provides specific exception types for different error conditions (connection, transport, protocol, command errors).

## Running the Examples

1.  **Install the Library:** Before running the examples, ensure you have installed the `uhf-rfid` library. For development and testing the examples, it's recommended to install it in editable mode from the root directory of the project:
    ```bash
    pip install -e .
    # Or with development dependencies (like pytest):
    # pip install -e ".[dev]"
    ```

2.  **Configure:** Check the `Configuration` section at the top of each example script (e.g., `01_connection.py`). You will likely need to change the `SERIAL_PORT` (e.g., to `/dev/ttyUSB0` on Linux or a different COM port on Windows) or the `TCP_HOST` and `TCP_PORT` to match your reader's settings.

3.  **Execute:** Run the desired example script using Python:
    ```bash
    # Example for the connection script
    python doc/examples/cph/01_connection.py

    # Example for the port scanner utility
    python doc/examples/utils/scan_ports.py
    ```
    *Note: You might need to adjust the path depending on your current working directory.* 

## Examples Structure

*   **`cph/`:** Contains examples specifically using the CPH protocol implementation (`CPHProtocol`). These demonstrate various `Reader` class functionalities:
    *   Connection & Disconnection (`01_connection.py`)
    *   Device Information & Control (`02_device_control.py`)
    *   Inventory & Tag Callbacks (`03_inventory.py`)
    *   Simple Parameter Management (`04_simple_params.py`)
    *   Tag Memory Operations (`05_tag_memory.py`)
    *   Tag Locking (`06_tag_lock.py`)
    *   Real-Time Clock (RTC) (`07_rtc.py`)
    *   Complex Parameter Sets (`08_complex_params.py`)
    *   Miscellaneous Commands (Relay, Audio) (`09_misc.py`)
*   **`utils/`:** Contains examples for utility functions provided by the library:
    *   Serial Port Scanner (`scan_ports.py`)

## Dependencies

*   **Core:**
    *   `pyserial-asyncio >= 0.6`: Required for the `SerialTransport`.
    *   Python `asyncio`: Part of the standard library (Python >= 3.8 recommended).
*   **Development/Testing (Optional):**
    *   `pytest`, `pytest-asyncio`: Used for running the test suite (install via `pip install -e .[dev]`). 