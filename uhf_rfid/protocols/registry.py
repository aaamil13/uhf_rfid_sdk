# uhf_rfid/protocols/registry.py

from typing import Dict, Type, Optional, List, Tuple
import logging

from uhf_rfid.protocols.base_protocol import BaseProtocol
from uhf_rfid.protocols.cph.protocol import CPHProtocol # Import the specific protocol

logger = logging.getLogger(__name__)

# Dictionary to store protocol classes, mapping name (str) to class (Type[BaseProtocol])
_protocol_registry: Dict[str, Type[BaseProtocol]] = {}

def register_protocol(name: str, protocol_class: Type[BaseProtocol]):
    """
    Registers a protocol class with a given name.

    Args:
        name: The name to register the protocol under (e.g., "cph_v4.0.1").
        protocol_class: The class object implementing BaseProtocol.

    Raises:
        ValueError: If the name is already registered or the class is invalid.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Protocol name must be a non-empty string.")
    if not isinstance(protocol_class, type) or not issubclass(protocol_class, BaseProtocol):
        raise ValueError(f"protocol_class must be a subclass of BaseProtocol, got {protocol_class}")

    if name in _protocol_registry:
        logger.warning(f"Protocol '{name}' is already registered. Overwriting with {protocol_class.__name__}.")
        # Or raise ValueError("Protocol name already registered.") if overwriting is disallowed

    logger.debug(f"Registering protocol '{name}' with class {protocol_class.__name__}")
    _protocol_registry[name] = protocol_class

def get_protocol_class(name: str) -> Optional[Type[BaseProtocol]]:
    """
    Retrieves a registered protocol class by name.

    Args:
        name: The name of the protocol to retrieve.

    Returns:
        The protocol class if found, otherwise None.
    """
    return _protocol_registry.get(name)

def create_protocol(name: str, *args, **kwargs) -> BaseProtocol:
    """
    Creates an instance of a registered protocol by name.

    Args:
        name: The name of the protocol to instantiate.
        *args: Positional arguments to pass to the protocol's constructor.
        **kwargs: Keyword arguments to pass to the protocol's constructor.

    Returns:
        An instance of the requested protocol.

    Raises:
        ValueError: If the protocol name is not registered.
        TypeError: If arguments passed are incorrect for the protocol's constructor.
    """
    protocol_class = get_protocol_class(name)
    if protocol_class is None:
        raise ValueError(f"Protocol '{name}' is not registered. Available: {list_protocols()}")

    try:
        logger.info(f"Creating instance of protocol '{name}' ({protocol_class.__name__})")
        # Instantiate the class with any provided arguments
        return protocol_class(*args, **kwargs)
    except Exception as e:
        logger.exception(f"Failed to instantiate protocol '{name}' with args={args}, kwargs={kwargs}: {e}")
        raise TypeError(f"Failed to instantiate protocol '{name}': {e}") from e


def list_protocols() -> list[str]:
    """Returns a list of names of all registered protocols."""
    return list(_protocol_registry.keys())

def get_installed_protocols() -> List[Dict[str, str]]:
    """
    Returns detailed information about all installed protocols.
    
    Returns:
        A list of dictionaries, each containing:
        - name: The registered protocol name
        - class_name: The name of the protocol class
        - version: Version information (if available in the protocol class)
        - description: Description of the protocol (if available)
    """
    protocols_info = []
    
    for name, protocol_class in _protocol_registry.items():
        info = {
            "name": name,
            "class_name": protocol_class.__name__
        }
        
        # Try to get version information if available
        if hasattr(protocol_class, "VERSION"):
            info["version"] = protocol_class.VERSION
        elif hasattr(protocol_class, "version"):
            info["version"] = protocol_class.version
        else:
            info["version"] = "Unknown"
            
        # Try to get description if available
        if hasattr(protocol_class, "DESCRIPTION"):
            info["description"] = protocol_class.DESCRIPTION
        elif hasattr(protocol_class, "description"):
            info["description"] = protocol_class.description
        else:
            # Use the class docstring if available
            info["description"] = protocol_class.__doc__ or "No description available"
            
        protocols_info.append(info)
        
    return protocols_info

# --- Auto-register known protocols ---
# Register the CPH protocol implemented in this library
try:
    # Use a descriptive name, potentially including version
    register_protocol("cph_v4.0.1", CPHProtocol)
except ValueError as e:
     # Should not happen on initial load unless there's a coding error above
     logger.error(f"Failed to auto-register CPH protocol: {e}")

# To add a new protocol later (e.g., in a separate file or plugin):
# 1. Define MyNewProtocol(BaseProtocol): ...
# 2. from uhf_rfid.protocols.registry import register_protocol
# 3. register_protocol("my_new_protocol_v1", MyNewProtocol)
