# doc/examples/cph/02_device_control.py
"""Example demonstrating basic device control commands.

This script shows how to:
1. Get the reader's version information.
2. (Commented out) Reset the reader to factory defaults.
3. (Commented out) Reboot the reader.
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
# from uhf_rfid.transport.tcp_transport import TcpTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port
# TCP_HOST = '192.168.1.190'
# TCP_PORT = 27011

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_device_commands():
    """Connects to the reader and executes device control commands."""
    transport = SerialTransport(port=SERIAL_PORT)
    # transport = TcpTransport(host=TCP_HOST, port=TCP_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        async with reader: # Use context manager for connection handling
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # 1. Get Version
            try:
                logger.info("--- Getting Reader Version ---")
                version_info = await reader.get_version()
                logger.info(f"  Software Version: {version_info.software_version}")
                logger.info(f"  Hardware Version: {version_info.hardware_version}")
                # Add other fields if available in DeviceInfo
            except UhfRfidError as e:
                logger.error(f"Error getting version: {e}")

            await asyncio.sleep(1)

            # 2. Set Default Parameters (Use with caution!)
            # This resets all reader settings to factory defaults.
            # Uncomment the following lines only if you are sure.
            # try:
            #     logger.warning("--- Setting Default Parameters (USE WITH CAUTION) ---")
            #     await reader.set_default_params()
            #     logger.info("Set default parameters command sent successfully.")
            #     # It might be good to re-read parameters or reboot after this
            # except UhfRfidError as e:
            #     logger.error(f"Error setting default parameters: {e}")

            # await asyncio.sleep(1)

            # 3. Reboot Reader
            # Uncomment the following lines to test reboot.
            # Note: After reboot, the connection will likely be lost.
            # try:
            #     logger.warning("--- Rebooting Reader ---")
            #     await reader.reboot_reader()
            #     logger.info("Reboot command sent successfully. Connection will likely drop.")
            #     # The script might terminate here or throw an error on subsequent commands
            #     # as the connection is lost.
            # except UhfRfidError as e:
            #     logger.error(f"Error sending reboot command: {e}")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting Device Control Example...")
    asyncio.run(run_device_commands())
    logger.info("Device Control Example finished.") 