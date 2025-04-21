# doc/examples/cph/04_simple_params.py
"""Example demonstrating getting and setting simple reader parameters.

This script shows how to manage:
1. Reader transmission power (get/set).
2. Reader buzzer status (get/set).
3. Tag filter time (get/set).

It reads the current value, sets a new value, verifies the change,
and then restores the original value for each parameter.
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_simple_param_commands():
    """Connects to the reader and executes get/set commands for simple parameters."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        async with reader: # Use context manager for connection handling
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Power --- 
            try:
                logger.info("--- Managing Power ---")
                # Get current power
                current_power = await reader.get_power()
                logger.info(f"  Current Power: {current_power} dBm")

                # Set new power (e.g., 20 dBm)
                new_power = 20
                logger.info(f"  Setting Power to: {new_power} dBm")
                await reader.set_power(new_power)
                logger.info("  Power set command sent.")

                # Verify new power
                power_after_set = await reader.get_power()
                logger.info(f"  Power after setting: {power_after_set} dBm")

                # Restore original power
                logger.info(f"  Restoring original power: {current_power} dBm")
                await reader.set_power(current_power)
                logger.info(f"  Original power restored.")

            except UhfRfidError as e:
                logger.error(f"Error managing power: {e}")

            await asyncio.sleep(1)

            # --- Buzzer --- 
            try:
                logger.info("--- Managing Buzzer ---")
                # Get current buzzer status
                current_status = await reader.get_buzzer_status()
                logger.info(f"  Current Buzzer Status: {'Enabled' if current_status else 'Disabled'}")

                # Toggle buzzer status
                new_status = not current_status
                logger.info(f"  Setting Buzzer Status to: {'Enabled' if new_status else 'Disabled'}")
                await reader.set_buzzer(new_status)
                logger.info("  Buzzer set command sent.")

                # Verify new status
                status_after_set = await reader.get_buzzer_status()
                logger.info(f"  Buzzer Status after setting: {'Enabled' if status_after_set else 'Disabled'}")

                # Restore original status
                logger.info(f"  Restoring original buzzer status: {'Enabled' if current_status else 'Disabled'}")
                await reader.set_buzzer(current_status)
                logger.info("  Original buzzer status restored.")

            except UhfRfidError as e:
                logger.error(f"Error managing buzzer: {e}")

            await asyncio.sleep(1)

            # --- Filter Time --- 
            try:
                logger.info("--- Managing Filter Time ---")
                # Get current filter time
                current_time = await reader.get_filter_time()
                logger.info(f"  Current Filter Time: {current_time} ms")

                # Set new filter time (e.g., 50 ms)
                # Note: CPH protocol often specifies this in seconds or another unit.
                # Here we assume the reader method takes milliseconds.
                new_time_ms = 50
                logger.info(f"  Setting Filter Time to: {new_time_ms} ms")
                await reader.set_filter_time(new_time_ms)
                logger.info("  Filter time set command sent.")

                # Verify new time
                time_after_set = await reader.get_filter_time()
                logger.info(f"  Filter Time after setting: {time_after_set} ms")

                # Restore original time
                logger.info(f"  Restoring original filter time: {current_time} ms")
                await reader.set_filter_time(current_time)
                logger.info("  Original filter time restored.")

            except UhfRfidError as e:
                logger.error(f"Error managing filter time: {e}")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting Simple Parameters Example...")
    asyncio.run(run_simple_param_commands())
    logger.info("Simple Parameters Example finished.") 