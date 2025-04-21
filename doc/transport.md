# Transport Layer

The `uhf_rfid` library uses a transport layer abstraction to handle the actual communication with the RFID reader. This allows you to easily switch between different communication methods like Serial (RS232/USB-Serial) and TCP/IP networking.

You specify the desired transport instance when creating the `Reader`.

## Available Transports

The following transport classes are available in `uhf_rfid.transport`:

### `SerialTransport`

Used for readers connected via a serial port (physical RS232 or a USB-to-Serial adapter).

**Initialization:**

```python
from uhf_rfid.transport import SerialTransport

# Example for Windows
serial_transport = SerialTransport(port="COM3", baudrate=115200)

# Example for Linux
# serial_transport = SerialTransport(port="/dev/ttyUSB0", baudrate=115200)
```

**Arguments:**

*   `port` (`str`): The device name of the serial port (e.g., `"COM3"` on Windows, `"/dev/ttyUSB0"` or `"/dev/ttyS0"` on Linux).
*   `baudrate` (`int`): The serial communication speed. This **must** match the reader's configured baud rate. Common values are `9600`, `19200`, `38400`, `57600`, `115200`.
*   `timeout` (`float`, optional): Read timeout in seconds. Defaults to `0.1`.

**Notes:**

*   Ensure you have the necessary permissions to access the serial port, especially on Linux (you might need to add your user to the `dialout` group).
*   Make sure the correct driver for your USB-to-Serial adapter is installed.

### `TcpTransport`

Used for readers connected via an Ethernet network.

**Initialization:**

```python
from uhf_rfid.transport import TcpTransport

tcp_transport = TcpTransport(host="192.168.1.200", port=6000)
```

**Arguments:**

*   `host` (`str`): The IP address or hostname of the RFID reader.
*   `port` (`int`): The TCP port number the reader is listening on. Consult the reader's configuration or documentation for this value (e.g., `6000` is common for CPH readers).
*   `timeout` (`float`, optional): Network connection and read timeout in seconds. Defaults to `5.0`.

**Notes:**

*   Ensure the reader is connected to the network and has a valid IP configuration.
*   Verify that no firewall is blocking the connection between your computer and the reader on the specified port.

### `MockTransport`

Used primarily for testing and development purposes. It simulates a connection without actually communicating with hardware.

**Initialization:**

```python
from uhf_rfid.transport import MockTransport

mock_transport = MockTransport()
```

**Functionality:**

*   The `MockTransport` allows you to enqueue predefined responses that will be returned when the `Reader` attempts to read data.
*   It records data that the `Reader` attempts to write.
*   This is useful for unit testing your application logic without needing a physical reader.

Refer to the test suite (`tests/`) for examples of how `MockTransport` is used.

## Choosing the Right Transport

Select the transport class (`SerialTransport` or `TcpTransport`) that matches how your RFID reader is physically connected to your system.

```python
from uhf_rfid import Reader, CphProtocol
from uhf_rfid.transport import SerialTransport, TcpTransport

# Option 1: Serial Connection
transport_serial = SerialTransport(port="COM3", baudrate=115200)
protocol_serial = CphProtocol(transport=transport_serial)
reader_serial = Reader(transport=transport_serial, protocol=protocol_serial)

# Option 2: TCP Connection
transport_tcp = TcpTransport(host="192.168.1.200", port=6000)
protocol_tcp = CphProtocol(transport=transport_tcp)
reader_tcp = Reader(transport=transport_tcp, protocol=protocol_tcp)

# Now use reader_serial or reader_tcp asynchronously
# async with reader_serial as reader:
#     # ... commands ...

# async with reader_tcp as reader:
#     # ... commands ...
``` 