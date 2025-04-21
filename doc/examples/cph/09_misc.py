# doc/examples/cph/09_misc.py
"""Example demonstrating miscellaneous reader commands.

This script shows how to:
1. Control the reader's relay (if equipped).
2. Send a command to play audio (if equipped and supported).
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import constants as cph_const # For RELAY constants
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_misc_commands():
    """Connects to the reader and executes miscellaneous commands."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        async with reader:
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Relay Operation --- 
            # Note: This requires the reader to physically have a controllable relay.
            try:
                logger.info("--- Controlling Relay ---")
                # Turn relay ON
                logger.info("  Turning relay ON...")
                await reader.relay_operation(cph_const.RELAY_ON)
                logger.info("  Relay ON command sent.")
                await asyncio.sleep(2)

                # Turn relay OFF
                logger.info("  Turning relay OFF...")
                await reader.relay_operation(cph_const.RELAY_OFF)
                logger.info("  Relay OFF command sent.")
                await asyncio.sleep(1)

                # Pulse relay (if supported by reader/constant)
                # logger.info("  Pulsing relay...")
                # await reader.relay_operation(cph_const.RELAY_PULSE)
                # logger.info("  Relay PULSE command sent.")
                # await asyncio.sleep(1)

            except UhfRfidError as e:
                logger.error(f"Error controlling relay: {e}")
            except AttributeError:
                 logger.warning("Relay constants (e.g., RELAY_PULSE) might not be defined, skipping pulse.")

            await asyncio.sleep(1)

            # --- Play Audio --- 
            # Note: This requires the reader to have audio playback capabilities.
            # The `audio_data` format depends on the reader (e.g., text, index, raw data).
            # CPH protocol often uses text (check encoding, e.g., utf-8 or gbk).
            try:
                logger.info("--- Playing Audio --- ")
                audio_text = "Tag Accepted"
                logger.info(f"  Sending audio text: '{audio_text}'")
                # Assuming UTF-8 encoding for the text
                await reader.play_audio(audio_text, encoding='utf-8')
                logger.info("  Play audio command sent.")

            except NotImplementedError:
                logger.warning("Audio playback might not be fully implemented in the protocol layer.")
            except UhfRfidError as e:
                logger.error(f"Error playing audio: {e}")

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting Miscellaneous Commands Example...")
    asyncio.run(run_misc_commands())
    logger.info("Miscellaneous Commands Example finished.") 