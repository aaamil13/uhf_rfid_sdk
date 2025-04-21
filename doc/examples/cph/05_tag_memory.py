# doc/examples/cph/05_tag_memory.py
"""Example demonstrating reading and writing tag memory banks.

This script shows how to:
1. Read data from a specified tag memory bank (e.g., EPC or USER).
2. Write data to the USER memory bank (with safety checks).
3. Verify the written data by reading it back.

Note: Requires a tag to be present in the reader's field.
Writing is restricted to the USER bank by default for safety.
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import constants as cph_const # For MEM_BANK constants
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError, CommandError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port
# Set these according to the tag you want to test with
TARGET_MEM_BANK = cph_const.MEM_BANK_EPC # Example: EPC bank
#TARGET_MEM_BANK = cph_const.MEM_BANK_USER # Example: User bank
WORD_ADDR = 2       # Starting word address (e.g., 2 for EPC data after CRC/PC)
WORD_COUNT_READ = 6 # Number of words (1 word = 2 bytes) to read
WORD_COUNT_WRITE = 2 # Number of words to write
DATA_TO_WRITE = b'\x12\x34\x56\x78' # 2 words (4 bytes) - MUST match WORD_COUNT_WRITE * 2
ACCESS_PASSWORD = None # Use None or a 4-byte hex string like "00000000" or "FFFFFFFF"

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_tag_memory_commands():
    """Connects to the reader and performs tag read/write operations."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    # Note: Tag memory operations often require a tag to be present in the field.
    # For reliable testing, you might need to perform an inventory first or ensure
    # a tag is placed consistently near the antenna.
    # These examples assume a tag is available.

    try:
        async with reader: # Use context manager for connection handling
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Read Tag Memory --- 
            try:
                logger.info(f"--- Reading Tag Memory ---")
                logger.info(f"  Target Bank: {TARGET_MEM_BANK}")
                logger.info(f"  Word Address: {WORD_ADDR}")
                logger.info(f"  Word Count: {WORD_COUNT_READ}")
                logger.info(f"  Access Password: {ACCESS_PASSWORD if ACCESS_PASSWORD else 'None'}")

                read_data = await reader.read_tag(
                    mem_bank=TARGET_MEM_BANK,
                    word_addr=WORD_ADDR,
                    word_count=WORD_COUNT_READ,
                    access_password=ACCESS_PASSWORD
                )
                logger.info(f"  Successfully Read Data (hex): {read_data.hex(' ').upper()}")

            except CommandError as e:
                # Specific errors like NO_TAG, PWD_ERROR, etc., might be returned here
                logger.error(f"CommandError reading tag: Status=0x{e.status_code:02X} ({e.error_message}) {e}")
            except UhfRfidError as e:
                logger.error(f"Error reading tag memory: {e}")

            await asyncio.sleep(1)

            # --- Write Tag Memory --- 
            # Warning: Writing to tags can permanently alter them. Be careful!
            # Writing to EPC bank (especially address 0/1) or Reserved bank can brick tags.
            # It's generally safer to test writing to the USER bank if available.
            if TARGET_MEM_BANK == cph_const.MEM_BANK_USER:
                try:
                    logger.info(f"--- Writing Tag Memory (USER BANK) ---")
                    logger.info(f"  Target Bank: {TARGET_MEM_BANK}")
                    logger.info(f"  Word Address: {WORD_ADDR}")
                    logger.info(f"  Word Count: {WORD_COUNT_WRITE}")
                    logger.info(f"  Data to Write (hex): {DATA_TO_WRITE.hex(' ').upper()}")
                    logger.info(f"  Access Password: {ACCESS_PASSWORD if ACCESS_PASSWORD else 'None'}")

                    await reader.write_tag(
                        mem_bank=TARGET_MEM_BANK,
                        word_addr=WORD_ADDR,
                        data=DATA_TO_WRITE,
                        access_password=ACCESS_PASSWORD
                    )
                    logger.info(f"  Successfully sent write command.")

                    # Optional: Verify write by reading back
                    await asyncio.sleep(0.5) # Short delay before reading back
                    logger.info("  Verifying write by reading back...")
                    verify_data = await reader.read_tag(
                        mem_bank=TARGET_MEM_BANK,
                        word_addr=WORD_ADDR,
                        word_count=WORD_COUNT_WRITE, # Read back the same number of words written
                        access_password=ACCESS_PASSWORD
                    )
                    logger.info(f"  Data Read Back (hex): {verify_data.hex(' ').upper()}")
                    if verify_data == DATA_TO_WRITE:
                        logger.info("  Verification SUCCESSFUL!")
                    else:
                        logger.warning("  Verification FAILED! Read data does not match written data.")

                except CommandError as e:
                    logger.error(f"CommandError writing tag: Status=0x{e.status_code:02X} ({e.error_message}) {e}")
                except UhfRfidError as e:
                    logger.error(f"Error writing tag memory: {e}")
            else:
                 logger.warning(f"Skipping write example because target bank is not USER bank ({TARGET_MEM_BANK}). Change TARGET_MEM_BANK to test writing.")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting Tag Memory Example...")
    # It might be useful to run inventory before this to ensure a tag is present
    # Or simply place a known tag on the reader before running.
    asyncio.run(run_tag_memory_commands())
    logger.info("Tag Memory Example finished.") 