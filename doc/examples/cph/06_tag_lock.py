# doc/examples/cph/06_tag_lock.py
"""Example demonstrating locking and killing tags.

This script shows how to:
1. Send a lock command using a specific lock payload and access password.
2. Send a kill command using the correct kill password.
3. Includes warnings about the potential permanence of locking and killing operations.

Note: Requires a tag to be present in the reader's field.
Lock and Kill commands are commented out by default for safety.
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError, CommandError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port

# --- Lock Configuration ---
# Warning: Locking tags can permanently restrict access.
# Choose the lock payload carefully based on the CPH protocol specification
# and the desired lock state (e.g., lock EPC write, lock User memory write, lock Kill password).
# Example: Lock User memory write permanently
LOCK_PAYLOAD = 0b00000100_00000011 # Action=perma-lock(3), Mask=User Write(1)
# Example: Lock EPC memory write with password
# LOCK_PAYLOAD = 0b00010000_00000010 # Action=pwd-lock(2), Mask=EPC Write(4)

# Access password required for locking operations (4-byte hex string)
# Usually the default is "00000000", but could be different if already set.
ACCESS_PASSWORD = "00000000"

# --- Kill Configuration ---
# WARNING: KILLING A TAG IS PERMANENT AND IRREVERSIBLE.
# Ensure you have the correct 32-bit (4-byte) Kill Password for the specific tag.
# Using the wrong password will fail, but attempting to kill is dangerous.
KILL_PASSWORD = "00000000" # 4-byte hex string Kill Password (DEFAULT IS OFTEN 00000000, BUT CAN BE CHANGED)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_tag_lock_kill_commands():
    """Connects to the reader and demonstrates the tag lock and kill commands."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    # Note: Lock/Kill operations require a tag to be present in the field.

    try:
        async with reader:
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Lock Tag --- 
            logger.warning("--- Attempting to Lock Tag (USE WITH CAUTION) ---")
            logger.warning(f"  Lock Payload: {LOCK_PAYLOAD:#018b} ({LOCK_PAYLOAD}) - Verify!")
            logger.warning(f"  Using Access Password: {ACCESS_PASSWORD}")
            # Uncomment the following block ONLY if you understand the LOCK_PAYLOAD
            # lock_command_enabled = False
            # if lock_command_enabled:
            #     try:
            #         await reader.lock_tag(
            #             lock_payload=LOCK_PAYLOAD,
            #             access_password=ACCESS_PASSWORD
            #         )
            #         logger.info(f"  Successfully sent lock command with payload {LOCK_PAYLOAD:#06x}.")
            #     except CommandError as e:
            #         logger.error(f"CommandError locking tag: Status=0x{e.status_code:02X} ({e.error_message}) {e}")
            #     except UhfRfidError as e:
            #         logger.error(f"Error locking tag: {e}")
            # else:
            #     logger.info("Lock command is disabled in script.")
            logger.info("Lock command is commented out by default for safety.")

            await asyncio.sleep(1)

            # --- Kill Tag --- 
            logger.warning("--- Attempting to Kill Tag (EXTREME CAUTION - IRREVERSIBLE) ---")
            logger.warning(f"  Using Kill Password: {KILL_PASSWORD} - VERIFY THIS IS CORRECT FOR THE TAG!")
            # Uncomment the following block ONLY IF YOU ARE ABSOLUTELY SURE and accept the risk.
            # kill_command_enabled = False
            # if kill_command_enabled:
            #     try:
            #         await reader.kill_tag(kill_password=KILL_PASSWORD)
            #         logger.info(f"  Successfully sent KILL command.")
            #     except CommandError as e:
            #         logger.error(f"CommandError killing tag: Status=0x{e.status_code:02X} ({e.error_message}) {e}")
            #     except UhfRfidError as e:
            #         logger.error(f"Error killing tag: {e}")
            # else:
            #     logger.info("Kill command is disabled in script.")
            logger.info("Kill command is commented out by default for safety.")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting Tag Lock/Kill Example...")
    asyncio.run(run_tag_lock_kill_commands())
    logger.info("Tag Lock/Kill Example finished.") 