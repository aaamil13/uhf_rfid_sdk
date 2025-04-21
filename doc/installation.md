# Installation Guide

This guide explains how to install the `uhf_rfid` library and its dependencies, and how to perform necessary platform-specific setup.

## Installation

### From Source (Recommended during development)

If you want to get the latest code from the repository, you can clone it and install in editable mode:

```bash
# Clone the repository
git clone https://github.com/aaamil13/uhf_rfid_sdk.git
cd uhf_rfid_sdk

# Install in editable mode
pip install -e .
```

This means changes you make to the source code will be immediately reflected when you run your scripts.

### From PyPI (If published)

If the library is published on the Python Package Index (PyPI), you can install it directly using pip:

```bash
pip install uhf-rfid # Replace uhf-rfid with the actual package name on PyPI
```

## Dependencies

*   **Python:** Python 3.7 or higher is recommended due to the use of `asyncio` and dataclasses.
*   **pyserial:** Required for communicating with readers via a serial port (RS232, USB-to-Serial).
    ```bash
    pip install pyserial
    ```
*   **asyncio:** Part of the standard Python library (no separate installation needed for Python 3.7+).

## Platform-Specific Setup

### 1. Physical Connection

Connect your UHF RFID reader to your computer using the appropriate method:

*   **Serial:** USB cable (which often creates a virtual serial port) or a direct RS232 cable.
*   **Network:** Ethernet cable connected to your local network.

### 2. Serial Port Configuration

If you are using a serial connection, you need to identify the correct serial port name and ensure you have the necessary permissions.

*   **Windows:**
    *   Serial ports are typically named `COM1`, `COM3`, `COM11`, etc.
    *   Open the **Device Manager** (search for it in the Start menu).
    *   Expand the **Ports (COM & LPT)** section.
    *   Look for your USB-to-Serial adapter or RFID reader. The port name (e.g., `COM3`) will be listed next to it.
    *   Use this name in the `SerialTransport` configuration (e.g., `port='COM3'`).
    *   Permissions are usually not an issue for standard users.

*   **Linux:**
    *   Serial ports usually have names like `/dev/ttyS0` (built-in), `/dev/ttyUSB0`, `/dev/ttyUSB1` (for USB-to-Serial adapters), or `/dev/ttyACM0` (common for some USB devices).
    *   You can list available ports using `ls /dev/tty*`.
    *   **Permissions:** By default, users often don't have direct access to serial ports. You typically need to add your user to a specific group (commonly `dialout`, but it might be `tty` or `uucp` on some systems).
        ```bash
        sudo usermod -a -G dialout $USER
        ```
        Replace `dialout` with the correct group name if necessary. **You will likely need to log out and log back in (or sometimes even restart) for the group change to take effect.**
    *   Use the full path in the `SerialTransport` configuration (e.g., `port='/dev/ttyUSB0'`).

### 3. Network Configuration

If you are using a TCP connection:

*   Ensure the RFID reader is connected to the same network as your computer.
*   Know the reader's **IP address** and the **TCP port** it listens on (for TCP Server mode on the reader) or the port it connects to (if the reader acts as a TCP Client).
*   Make sure your computer can reach the reader's IP address (e.g., using `ping`).
*   Configure any **firewalls** on your computer or network to allow traffic on the specified TCP port between your computer and the reader.
*   Use the correct host IP and port in the `TcpTransport` configuration (e.g., `host='192.168.1.178', port=6000`). 