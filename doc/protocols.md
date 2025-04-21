# Protocol Implementation

The `uhf_rfid` library is designed with a modular architecture that allows easy addition of support for different RFID protocols. The library currently supports the CPH protocol version 4.0.1, but you can implement and add your own protocols for communication with other RFID readers.

## Protocol Architecture

The protocol system of `uhf_rfid` is based on the following principles:

1. An abstract base class `BaseProtocol` defines the common interface.
2. Concrete implementations like `CPHProtocol` inherit from the base class.
3. A system for registering and discovering protocols via `registry.py`.
4. Delegation of specific commands to separate modules for improved code organization.

## Implementing a New Protocol

### 1. Creating the Package Structure

It's good practice to organize your protocol into a separate package:

```
uhf_rfid/
└── protocols/
    ├── base_protocol.py
    ├── registry.py 
    ├── framing.py
    ├── your_protocol/
    │   ├── __init__.py
    │   ├── protocol.py         # Main implementation
    │   ├── constants.py        # Constants and command codes
    │   ├── commands_device.py  # Functions for device-related commands
    │   ├── commands_tags.py    # Functions for tag-related commands
    │   └── parameters.py       # Classes for structuring parameters
    └── cph/
        └── ...
```

### 2. Implementing the Main Protocol Class

Create a class that inherits from `BaseProtocol` and implements all abstract methods. See `CPHProtocol` as an example:

```python
# uhf_rfid/protocols/your_protocol/protocol.py

from uhf_rfid.protocols.base_protocol import BaseProtocol, DeviceInfo, TagReadData

class YourProtocol(BaseProtocol):
    """
    Implements your specific RFID Communication Protocol.
    """
    VERSION = "1.0.0"
    DESCRIPTION = "Your protocol implementation for XYZ RFID readers."

    # Implement all abstract methods from BaseProtocol
    
    def encode_command(self, command_code: int, address: int = 0x0000, params_data: bytes = b'') -> bytes:
        # Transform the command code, address, and data into the outgoing byte format
        # ...
        
    def parse_frame(self, data: bytes) -> Tuple[Optional[bytes], bytes]:
        # Analyze incoming data and extract a complete frame if available
        # ...
    
    # ... and the rest of the abstract methods
```

### 3. Organizing Command Functions

For better organization, separate the command implementation by functional areas:

```python
# uhf_rfid/protocols/your_protocol/commands_device.py

def encode_get_version_request() -> bytes:
    # Protocol-specific implementation
    return b''

def decode_get_version_response(parsed_params: Dict[Any, Any]) -> DeviceInfo:
    # Extract device information from the response
    # ...
    return DeviceInfo(
        software_version=sw_version,
        hardware_version=hw_version,
        # ...
    )
```

### 4. Registering Your Protocol

In the main module of your protocol or during initialization, register it:

```python
# In uhf_rfid/protocols/your_protocol/__init__.py
# or elsewhere in your code

from uhf_rfid.protocols.registry import register_protocol
from uhf_rfid.protocols.your_protocol.protocol import YourProtocol

# Register the protocol with a unique name (including version)
register_protocol("your_protocol_v1.0", YourProtocol)
```

## Key Concepts for Implementation

### Command Encoding/Decoding

The protocol implementation must:

1. **Transform** abstract commands (like "get version") into a protocol-specific byte format.
2. **Parse** responses from the device back into useful data structures.
3. **Handle errors** and validate data.

### Parameter Handling

Most protocols use specific formats for parameters, such as:
- TLV (Type-Length-Value)
- Fixed fields with specific offsets
- JSON or XML for more modern devices

Implement appropriate functions for packing/unpacking parameters according to your protocol's requirements.

### Error Handling

Ensure proper error handling and exceptions:

```python
def decode_get_power_response(self, parsed_params: Dict[Any, Any]) -> int:
    if 'power' not in parsed_params:
        raise ProtocolError("Missing power parameter in response")
    
    power_value = parsed_params['power']
    if not isinstance(power_value, int) or power_value < 0 or power_value > 30:
        raise ProtocolError(f"Invalid power value: {power_value}")
    
    return power_value
```

## Using Protocols in main v0.2.0

After installing the `uhf_rfid` library v0.2.0, you can use the built-in CPH protocol like this:

```python
import asyncio
from uhf_rfid.core.reader import Reader
from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.registry import create_protocol

async def main():
    # Create transport
    transport = SerialTransport(port="COM3", baudrate=115200)
    
    # Create protocol
    protocol = create_protocol("cph_v4.0.1")
    
    # Create reader with the standard CPH protocol
    reader = Reader(transport, protocol)
    
    # Use the library's API
    await reader.connect()
    version = await reader.get_version()
    print(f"Connected to: {version.model} (Software: {version.software_version})")
    
    # Basic tag operations
    await reader.start_inventory()
    await asyncio.sleep(2)  # Allow time for tag reading
    await reader.stop_inventory()
    
    await reader.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Contributing to the Library

If you have implemented a new protocol that could be useful to others, please consider:

1. Creating a pull request to the main repository.
2. Providing adequate test coverage for your implementation.
3. Documenting the specifics of your protocol.

New protocol implementations will expand the `uhf_rfid` ecosystem and make the library more useful for the community. 