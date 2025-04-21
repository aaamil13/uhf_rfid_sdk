# doc/examples/cph/03_inventory.py
"""Example demonstrating inventory commands and tag notification callbacks.

This script shows how to:
1. Register an asynchronous callback function to handle tag notifications.
2. Start continuous inventory, wait for a duration or Ctrl+C, and stop it.
3. Perform a single inventory burst.
4. Unregister the callback function.
5. Handle signals (Ctrl+C) for graceful shutdown.
"""

import asyncio
import logging
import signal

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError
from uhf_rfid.protocols.base_protocol import TagReadData # For type hinting callback

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port
CONTINUOUS_INVENTORY_DURATION = 10 # Seconds to run continuous inventory

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Callback Function --- 
# def tag_seen_count = 0 # Incorrect syntax for global variable
tag_seen_count = 0 # Initialize simple counter at module level

async def my_tag_handler(tag: TagReadData):
    """Asynchronous callback function executed for each tag notification.

    Args:
        tag: A TagReadData object containing information about the seen tag.
    """
    global tag_seen_count
    tag_seen_count += 1
    logger.info(f"[TAG SEEN #{tag_seen_count}] EPC: {tag.epc} | RSSI: {tag.rssi} | Ant: {tag.antenna} | TID: {tag.tid}")
    # You can add more complex logic here, like storing tags, checking against a list, etc.

async def run_inventory_commands():
    """Connects to the reader and runs inventory examples."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    stop_event = asyncio.Event() # Event to signal stopping continuous inventory

    # --- Signal Handling (for graceful shutdown on Ctrl+C) --- 
    loop = asyncio.get_running_loop()
    def signal_handler():
        logger.warning("Ctrl+C detected, setting stop event...")
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
    except NotImplementedError:
        # Signal handling might not be available on all platforms (e.g., Windows sometimes)
        logger.warning("Signal handling for SIGINT not available on this platform.")


    try:
        async with reader: # Use context manager for connection handling
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Register Callback --- 
            logger.info("Registering tag notification callback...")
            await reader.register_tag_notify_callback(my_tag_handler)
            logger.info("Callback registered.")

            # --- Example 1: Continuous Inventory --- 
            logger.info(f"--- Starting Continuous Inventory for {CONTINUOUS_INVENTORY_DURATION} seconds ---")
            try:
                global tag_seen_count
                tag_seen_count = 0 # Reset counter
                await reader.start_inventory()
                logger.info("Continuous inventory started. Waiting for tags or stop signal...")
                
                # Wait for a duration or until Ctrl+C is pressed
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=CONTINUOUS_INVENTORY_DURATION)
                    logger.info("Stop event received.")
                except asyncio.TimeoutError:
                    logger.info(f"Inventory duration ({CONTINUOUS_INVENTORY_DURATION}s) elapsed.")
                
                logger.info("Stopping continuous inventory...")
                await reader.stop_inventory()
                logger.info("Continuous inventory stopped.")

            except UhfRfidError as e:
                logger.error(f"Error during continuous inventory: {e}")
                # Ensure stop is called if start succeeded but error occurred later
                try:
                    await reader.stop_inventory()
                except UhfRfidError as stop_e:
                    logger.error(f"Error trying to stop inventory after error: {stop_e}")
            
            await asyncio.sleep(2) # Pause before next example
            stop_event.clear() # Clear event for next potential use

            # --- Example 2: Single Burst Inventory --- 
            # This command typically triggers notifications for tags seen in one burst.
            logger.info("--- Performing Single Burst Inventory (Active Inventory) ---")
            try:
                tag_seen_count = 0 # Reset counter
                await reader.inventory_single_burst() # Corresponds to CMD_ACTIVE_INVENTORY
                logger.info("Single burst command sent. Waiting briefly for potential notifications...")
                await asyncio.sleep(2) # Allow some time for notifications to arrive
                logger.info(f"Single burst finished. Tags seen in burst: {tag_seen_count}")
            except UhfRfidError as e:
                logger.error(f"Error during single burst inventory: {e}")
            
            # --- Unregister Callback --- 
            logger.info("Unregistering tag notification callback...")
            await reader.unregister_tag_notify_callback(my_tag_handler)
            logger.info("Callback unregistered.")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        # Clean up signal handler
        try:
            loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            pass # Ignore if not implemented
        logger.info("Inventory example finished.")


if __name__ == "__main__":
    logger.info("Starting Inventory Example...")
    asyncio.run(run_inventory_commands()) 