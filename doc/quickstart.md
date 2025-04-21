# Quickstart Guide

This example demonstrates the basic steps to connect to a reader, start inventory, receive tag notifications, and read a simple parameter.

```python
import asyncio
import logging
from typing import Any

# Core components
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.status import ConnectionStatus
from uhf_rfid.core.exceptions import CommandError, UhfRfidError

# Protocol implementation (CPH in this case)
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import constants as cph_const

# Transport layers (choose one)
from uhf_rfid.transport.serial_async import SerialTransport
# from uhf_rfid.transport.tcp_async import TcpTransport

# --- Configuration ---
# Set up logging (optional but recommended)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("Quickstart")

# Connection settings (MODIFY THESE)
SERIAL_PORT = 'COM3'         # For Windows. Linux: '/dev/ttyUSB0' etc.
SERIAL_BAUD_RATE = 115200

# TCP Alternative (uncomment and modify if using TCP)
# READER_HOST = '192.168.1.178' # Reader's IP address
# READER_PORT = 6000           # Reader's TCP port

# Timeout for reader responses (seconds)
RESPONSE_TIMEOUT = 5.0

# --- Tag Callback Function ---
def simple_tag_callback(frame_type: int, address: int, frame_code: int, params: Any):
    """Callback function executed when a tag notification is received."""
    logger.info(f"Notification Received: Type={frame_type}, Addr={address:#06x}, Code={frame_code:#04x}")
    
    # Check if it's a tag upload notification
    if frame_code in [cph_const.NOTIF_TAG_UPLOADED, cph_const.NOTIF_OFFLINE_TAG_UPLOADED]:
        try:
            # Extract EPC from the nested structure
            tag_data = params.get(cph_const.TAG_SINGLE_TAG, {})
            epc = tag_data.get(cph_const.TAG_EPC, "N/A")
            rssi = tag_data.get(cph_const.TAG_RSSI, None)
            rssi_str = f" (RSSI: {rssi})" if rssi is not None else ""
            logger.info(f"  ---> Tag Found: EPC={epc}{rssi_str}")
        except Exception as e:
            logger.error(f"  Error parsing tag data: {e} - Raw Params: {params}")
    else:
        logger.info(f"  Other notification data: {params}")

# --- Status Change Callback (Optional) ---
def connection_status_callback(status: ConnectionStatus):
    """Callback function executed when the connection status changes."""
    logger.info(f"Reader Connection Status changed to: {status.name}")

# --- Main Async Function ---
async def run_reader():
    """Main function to run the reader operations."""
    
    # 1. Initialize Transport Layer (Choose one)
    # transport = SerialTransport(port=SERIAL_PORT, baudrate=SERIAL_BAUD_RATE)
    transport = SerialTransport(port=SERIAL_PORT, baudrate=SERIAL_BAUD_RATE)
    # transport = TcpTransport(host=READER_HOST, port=READER_PORT)
    
    # 2. Initialize Protocol Layer
    protocol = CPHProtocol()
    
    # 3. Initialize Reader Core
    reader = Reader(transport, protocol, response_timeout=RESPONSE_TIMEOUT)
    
    # 4. (Optional) Register status change callback
    reader.set_status_change_callback(connection_status_callback)
    
    try:
        # 5. Connect to the reader (using async context manager for auto-disconnect)
        async with reader: # Handles connect() and disconnect() automatically
            logger.info("Successfully connected to the reader.")
            
            # 6. Register the tag notification callback
            logger.info("Registering tag notification callback...")
            await reader.register_tag_notify_callback(simple_tag_callback)
            
            # 7. Read a simple parameter (e.g., current power)
            try:
                power = await reader.get_power()
                logger.info(f"Reader current power: {power} dBm")
            except CommandError as e:
                logger.error(f"Failed to get power: {e.status_code:#04x} ({e.get_status_message()})")
            except UhfRfidError as e:
                logger.error(f"Error getting power: {e}")
                
            # 8. Start inventory
            logger.info("Starting inventory...")
            await reader.start_inventory()
            logger.info("Inventory started. Listening for tags for 15 seconds...")
            
            # 9. Keep running to receive tags (adjust sleep time as needed)
            await asyncio.sleep(15)
            
            # 10. Stop inventory
            logger.info("Stopping inventory...")
            await reader.stop_inventory()
            logger.info("Inventory stopped.")
            
            # 11. Unregister callback (optional, but good practice if reusing reader)
            # await reader.unregister_callback(simple_tag_callback)
            
            # Give a moment before disconnecting
            await asyncio.sleep(1)
            
    except UhfRfidError as e:
        logger.exception(f"RFID Library Error: {e}")
    except ConnectionError as e:
        logger.exception(f"Connection Error: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        # The async context manager handles disconnection, but we log it
        logger.info("Reader operations finished or error occurred.")

# --- Run the Main Function ---
if __name__ == "__main__":
    logger.info("Starting Quickstart Example...")
    asyncio.run(run_reader())
    logger.info("Quickstart Example finished.")

```

**To run this:**

1.  Save the code as a Python file (e.g., `quickstart_example.py`).
2.  Make sure you have installed the `uhf_rfid` library and `pyserial` (see [Installation Guide](installation.md)).
3.  **Modify the `SERIAL_PORT` or `READER_HOST`/`READER_PORT` variables** at the top to match your reader's connection details.
4.  Run the script from your terminal: `python quickstart_example.py`
5.  Ensure an RFID tag is within the reader's range during the inventory period.

You should see log messages indicating connection, callback registration, power reading, inventory start/stop, and any tags found during the inventory. 