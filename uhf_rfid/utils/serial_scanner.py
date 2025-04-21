# uhf_rfid/utils/serial_scanner.py
"""Utility to scan for available serial ports and check their status."""

import sys
import logging
import serial
import serial.tools.list_ports
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class PortInfo:
    """Represents information about a detected serial port."""
    device: str                   # Port name (e.g., COM3, /dev/ttyUSB0)
    name: str                     # Short name
    description: str              # Human-readable description
    hwid: str                     # Hardware ID string
    vid: Optional[int] = None     # Vendor ID
    pid: Optional[int] = None     # Product ID
    serial_number: Optional[str] = None
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    interface: Optional[str] = None
    accessible: bool = False      # Whether the port could be opened successfully
    error: Optional[str] = None   # Error message if opening failed

def _check_port_access(port_name: str) -> tuple[bool, Optional[str]]:
    """Tries to open a port to check accessibility.

    Args:
        port_name: The name of the port device (e.g., 'COM3').

    Returns:
        A tuple (accessible: bool, error_message: Optional[str]).
    """
    try:
        # Try opening and closing the port with a short timeout
        s = serial.Serial(port=port_name, timeout=0.1)
        s.close()
        return True, None
    except serial.SerialException as e:
        # Common errors:
        err_msg = str(e)
        if "Permission denied" in err_msg or "Access is denied" in err_msg:
             return False, "Permission denied"
        elif "FileNotFoundError" in err_msg or "could not be found" in err_msg:
             return False, "Device not found"
        elif "Device or resource busy" in err_msg:
             return False, "Busy"
        else:
             logger.debug(f"SerialException checking port {port_name}: {e}")
             return False, f"Cannot open ({type(e).__name__})"
    except Exception as e:
        logger.warning(f"Unexpected error checking port {port_name}: {e}", exc_info=False)
        return False, f"Unexpected error ({type(e).__name__})"

def scan_serial_ports(check_access: bool = True) -> List[PortInfo]:
    """Scans for available serial ports and returns detailed information.

    Args:
        check_access: If True, attempts to open each port briefly to check
                      read/write permissions.

    Returns:
        A list of PortInfo objects.
    """
    ports_found: List[PortInfo] = []
    comports = serial.tools.list_ports.comports()

    for port in comports:
        logger.debug(f"Found port: {port.device}")
        # Safely convert attributes to the expected types for PortInfo
        device = str(port.device) if port.device is not None else ""
        name = str(port.name) if port.name is not None else ""
        description = str(port.description) if port.description is not None else ""
        hwid = str(port.hwid) if port.hwid is not None else ""
        serial_number = str(port.serial_number) if port.serial_number is not None else None
        location = str(port.location) if port.location is not None else None
        manufacturer = str(port.manufacturer) if port.manufacturer is not None else None
        product = str(port.product) if port.product is not None else None
        interface = str(port.interface) if port.interface is not None else None
        
        # Safely convert VID/PID to int, default to None on failure
        vid: Optional[int] = None
        try:
            if port.vid is not None:
                vid = int(port.vid) # Or int(port.vid, 16) if format is hex string?
        except (ValueError, TypeError):
            logger.warning(f"Could not parse VID '{port.vid}' as int for port {device}")
            vid = None
            
        pid: Optional[int] = None
        try:
            if port.pid is not None:
                pid = int(port.pid)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse PID '{port.pid}' as int for port {device}")
            pid = None

        accessible = False
        access_error: Optional[str] = None

        if check_access:
            accessible, access_error = _check_port_access(device)
            logger.debug(f"Access check for {device}: Accessible={accessible}, Error={access_error}")

        ports_found.append(PortInfo(
            device=device,
            name=name,
            description=description,
            hwid=hwid,
            vid=vid,
            pid=pid,
            serial_number=serial_number,
            location=location,
            manufacturer=manufacturer,
            product=product,
            interface=interface,
            accessible=accessible,
            error=access_error
        ))

    logger.info(f"Scan complete. Found {len(ports_found)} ports.")
    return ports_found

# Basic example usage if run directly
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print("Scanning for serial ports (checking access, may take a moment)...")
    ports = scan_serial_ports(check_access=True)

    if not ports:
        print("No ports found.")
    else:
        print(f"Found {len(ports)} ports:")
        for p in ports:
            print(f"\nDevice:       {p.device}")
            print(f"  Name:         {p.name}")
            print(f"  Description:  {p.description}")
            print(f"  HWID:         {p.hwid}")
            if p.vid and p.pid:
                 print(f"  VID:PID:      {p.vid:04X}:{p.pid:04X}")
            if p.serial_number:
                 print(f"  Serial:       {p.serial_number}")
            if p.manufacturer:
                 print(f"  Manufacturer: {p.manufacturer}")
            if p.product:
                 print(f"  Product:      {p.product}")
            if p.location:
                 print(f"  Location:     {p.location}")
            if p.interface:
                 print(f"  Interface:    {p.interface}")
            # Status based on access check
            status_str = "Accessible" if p.accessible else f"Not Accessible ({p.error})"
            print(f"  Status:       {status_str}") 