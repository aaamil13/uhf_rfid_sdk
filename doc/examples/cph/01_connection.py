# doc/examples/cph/01_connection.py
"""Example demonstrating various ways to connect to and disconnect from an RFID reader.

This script shows:
1. Connecting/disconnecting using SerialTransport.
2. Connecting/disconnecting using TcpTransport.
3. Using the Reader as an asynchronous context manager for automatic connection handling.
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.transport.tcp_transport import TcpTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import ConnectionError, UhfRfidError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port (e.g., '/dev/ttyUSB0' on Linux)
TCP_HOST = '192.168.1.190' # Change to your reader's IP address
TCP_PORT = 27011          # Default CPH TCP port

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def serial_connection_example():
    """Demonstrates connecting and disconnecting using SerialTransport."""
    logger.info("--- Serial Connection Example ---")
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        logger.info(f"Attempting to connect to reader on {SERIAL_PORT}...")
        await reader.connect()
        logger.info(f"Successfully connected! Reader status: {reader.state.name}")

        # --- Perform some actions while connected (optional) ---
        # Example: Get version
        try:
            version_info = await reader.get_version()
            logger.info(f"Reader Version Info: SW={version_info.software_version}, HW={version_info.hardware_version}")
        except UhfRfidError as e:
            logger.error(f"Error getting version: {e}")
        # --- End actions ---

        logger.info("Disconnecting from reader...")
        await reader.disconnect()
        logger.info(f"Successfully disconnected. Reader status: {reader.state.name}")

    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        # Ensure disconnect is called even if errors occurred during operations
        if reader.is_connected:
            logger.warning("Disconnecting reader in finally block...")
            await reader.disconnect()

async def tcp_connection_example():
    """Demonstrates connecting and disconnecting using TcpTransport."""
    logger.info("\n--- TCP Connection Example ---") # Keep \n here for line break in output
    transport = TcpTransport(host=TCP_HOST, port=TCP_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        logger.info(f"Attempting to connect to reader at {TCP_HOST}:{TCP_PORT}...")
        await reader.connect()
        logger.info(f"Successfully connected! Reader status: {reader.state.name}")

        # Perform actions...

        logger.info("Disconnecting from reader...")
        await reader.disconnect()
        logger.info(f"Successfully disconnected. Reader status: {reader.state.name}")

    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        if reader.is_connected:
            logger.warning("Disconnecting reader in finally block...")
            await reader.disconnect()


async def context_manager_example():
    """Demonstrates using the Reader as an asynchronous context manager.

    The `async with Reader(...)` statement automatically handles calling
    `reader.connect()` on entry and `reader.disconnect()` on exit,
    even if errors occur within the block.
    """
    logger.info("\n--- Context Manager Example (Serial) ---") # Keep \n here
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()

    try:
        # The context manager handles connect() and disconnect() automatically
        async with Reader(transport=transport, protocol=protocol) as reader:
            logger.info(f"Connected via context manager. Status: {reader.state.name}")
            logger.info(f"Reader is connected: {reader.is_connected}")

            # Perform actions within the 'with' block
            version_info = await reader.get_version()
            logger.info(f"Reader Version Info: SW={version_info.software_version}, HW={version_info.hardware_version}")

        # After exiting the 'with' block, disconnect is automatically called
        logger.info(f"Exited context manager. Reader should be disconnected.")
        # Note: Accessing reader attributes after exit might not reflect the final state
        # logger.info(f"Reader status after exit (may be unreliable): {reader.state.name}") # Status might be DISCONNECTING or DISCONNECTED

    except ConnectionError as e:
        logger.error(f"Connection failed within context manager: {e}")
    except UhfRfidError as e:
        logger.error(f"An RFID error occurred within context manager: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred within context manager: {e}")


async def main():
    """Runs all connection examples sequentially."""
    await serial_connection_example()
    await asyncio.sleep(1) # Pause briefly between examples
    await tcp_connection_example()
    await asyncio.sleep(1)
    await context_manager_example()

if __name__ == "__main__": # Correct syntax
    asyncio.run(main()) 