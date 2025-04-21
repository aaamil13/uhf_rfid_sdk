# doc/examples/utils/scan_ports.py
"""Example script demonstrating how to use the serial port scanner."""

import logging
from typing import List # Import List for type hinting

# Adjust the import path based on your project structure
# Assuming 'uhf_rfid' is in the Python path
from uhf_rfid.utils.serial_scanner import scan_serial_ports, PortInfo

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def display_ports(ports: List[PortInfo]):
    """Helper function to display port information in a formatted way."""
    if not ports:
        print("  No ports found.")
        return

    print(f"  Found {len(ports)} ports:")
    for p in ports:
        print(f"\n  Device:       {p.device}")
        print(f"    Name:         {p.name}")
        print(f"    Description:  {p.description}")
        print(f"    HWID:         {p.hwid}")
        if p.vid and p.pid:
             print(f"    VID:PID:      {p.vid:04X}:{p.pid:04X}")
        if p.serial_number:
             print(f"    Serial:       {p.serial_number}")
        if p.manufacturer:
             print(f"    Manufacturer: {p.manufacturer}")
        if p.product:
             print(f"    Product:      {p.product}")
        if p.location:
             print(f"    Location:     {p.location}")
        if p.interface:
             print(f"    Interface:    {p.interface}")
        # Status only relevant if check_access was True during scan
        if p.error is not None or p.accessible:
            status_str = "Accessible" if p.accessible else f"Not Accessible ({p.error})"
            print(f"    Status:       {status_str}")
        else:
            # If check_access was False, accessibility wasn't determined
            print(f"    Status:       Access Not Checked")


if __name__ == '__main__':
    print("--- Serial Port Scanner Example ---")

    print("\nScanning ports (with access check, may take a moment)...")
    ports_with_check = scan_serial_ports(check_access=True)
    display_ports(ports_with_check)

    print("\nScanning ports (WITHOUT access check)...")
    ports_without_check = scan_serial_ports(check_access=False)
    display_ports(ports_without_check)

    print("\n--- Finished ---") 