# doc/examples/cph/07_rtc.py
"""Example demonstrating Real-Time Clock (RTC) commands.

This script shows how to:
1. Get the current time from the reader's RTC.
2. Set the reader's RTC to the current system time.
3. Verify the time after setting it.
"""

import asyncio
import logging
import datetime

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_rtc_commands():
    """Connects to the reader and executes RTC get/set commands."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        async with reader:
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Get RTC Time --- 
            try:
                logger.info("--- Getting RTC Time ---")
                current_rtc_time = await reader.get_rtc_time()
                logger.info(f"  Current Reader RTC Time: {current_rtc_time.strftime('%Y-%m-%d %H:%M:%S')}")
            except UhfRfidError as e:
                logger.error(f"Error getting RTC time: {e}")

            await asyncio.sleep(1)

            # --- Set RTC Time --- 
            # Sets the reader's clock to the current time of the computer running the script.
            try:
                logger.info("--- Setting RTC Time --- ")
                time_to_set = datetime.datetime.now()
                logger.info(f"  Setting Reader RTC Time to current system time: {time_to_set.strftime('%Y-%m-%d %H:%M:%S')}")
                await reader.set_rtc_time(time_to_set)
                logger.info("  Set RTC time command sent.")

                # Verify time after setting
                await asyncio.sleep(0.5) # Small delay before reading back
                time_after_set = await reader.get_rtc_time()
                logger.info(f"  Reader RTC Time after setting: {time_after_set.strftime('%Y-%m-%d %H:%M:%S')}")
                # Note: There might be a slight difference due to command execution time.

            except UhfRfidError as e:
                logger.error(f"Error setting RTC time: {e}")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting RTC Example...")
    asyncio.run(run_rtc_commands())
    logger.info("RTC Example finished.") 