# examples/identify_tag_example.py
import asyncio
import logging
import sys

# Adjust the path to import from the root directory if running directly
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from uhf_rfid.transport import MockTransport
from uhf_rfid.core.reader import Reader
from uhf_rfid.protocols.cph import CphProtocol # Assuming CPH protocol
from uhf_rfid.utils.tag_utils import identify_tag

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # --- Setup Reader with MockTransport ---
    # MockTransport allows simulating reader responses without real hardware.
    # We need to tell it what TID data to return when read_tag is called.
    
    # Example TID for Impinj Monza R6-P (MDID=1, TMN=437)
    # TID = E2 01 2D 15
    mock_tid_r6p = bytes([0xE2, 0x01, 0x2D, 0x15]) 

    # Example TID for Alien Higgs 3 (MDID=2, TMN=218)
    # TID = E2 02 15 A?
    # MDID = 2 (0x002) -> Byte1=0x00, Byte2[7:4]=0x02 -> 0x00, 0x20
    # TMN = 218 (0xDA) -> Byte2[3:0]=0x0D, Byte3=0x0A -> 0x2D, 0x0A ? NO
    # TMN = 218 (0x0DA) -> Byte2[3:0]=0x00, Byte3=0xDA -> 0x20, 0xDA
    # TID = E2 00 20 DA
    mock_tid_higgs3 = bytes([0xE2, 0x00, 0x20, 0xDA])

    # Configure mock responses: Map EPC -> command -> response_data
    # Here we only mock the read_tag command for the TID bank
    mock_responses = {
        "300000000000000000000001": { # EPC 1
            (cph_const.CMD_READ_TAG_DATA, cph_const.MEM_BANK_TID, 0, 2): mock_tid_r6p 
        },
        "300000000000000000000002": { # EPC 2
            (cph_const.CMD_READ_TAG_DATA, cph_const.MEM_BANK_TID, 0, 2): mock_tid_higgs3
        },
        "300000000000000000000003": { # EPC 3 (will simulate read error)
            (cph_const.CMD_READ_TAG_DATA, cph_const.MEM_BANK_TID, 0, 2): RFIDError("Mock Read Error")
        }
    }
    # Need to import constants and RFIDError for the above dict
    from uhf_rfid.protocols.cph import constants as cph_const
    from uhf_rfid.core.exceptions import RFIDError
    
    # Recreate dict with imports resolved
    mock_responses = {
        "300000000000000000000001": { # EPC 1
            (cph_const.CMD_READ_TAG_DATA, cph_const.MEM_BANK_TID, 0, 2): mock_tid_r6p 
        },
        "300000000000000000000002": { # EPC 2
            (cph_const.CMD_READ_TAG_DATA, cph_const.MEM_BANK_TID, 0, 2): mock_tid_higgs3
        },
        "300000000000000000000003": { # EPC 3 (will simulate read error)
            (cph_const.CMD_READ_TAG_DATA, cph_const.MEM_BANK_TID, 0, 2): RFIDError("Mock Read Error")
        }
    }

    transport = MockTransport(responses=mock_responses)
    protocol = CphProtocol(transport=transport)
    reader = Reader(protocol=protocol)

    # --- Simulate reading some EPCs ---
    # In a real scenario, you would get these from reader.inventory() or similar
    discovered_epcs = [
        "300000000000000000000001", # Impinj Monza R6-P
        "300000000000000000000002", # Alien Higgs 3
        "300000000000000000000003", # Tag causing read error
        "300000000000000000000004"  # Unknown TID (not mocked, will raise error in mock)
    ]

    logger.info("Attempting to identify discovered tags...")

    for epc in discovered_epcs:
        logger.info(f"--- Identifying EPC: {epc} ---")
        try:
            tag_details = await identify_tag(reader, epc)
            
            if tag_details.get("error"):
                logger.error(f"  Error identifying tag: {tag_details['error']}")
                if tag_details.get("tid_raw"):
                     logger.error(f"  Raw TID read: {tag_details['tid_raw']}")
            elif tag_details.get("tag_info"):
                info = tag_details["tag_info"]
                logger.info(f"  Manufacturer: {info.get('manufacturer_name', 'N/A')}")
                logger.info(f"  Model: {info.get('model_name', 'N/A')}")
                logger.info(f"  Memory (bits): {info.get('memory')}")
                logger.info(f"  Features: {info.get('features')}")
                logger.info(f"  Notes: {info.get('notes')}")
                logger.debug(f"  Raw TID: {tag_details['tid_raw']}") # Debug
            else:
                # Parsed TID but no definition found
                logger.warning(f"  Could not find definition for tag.")
                logger.warning(f"  Manufacturer ID: {tag_details.get('manufacturer_id')}")
                logger.warning(f"  Model Number: {tag_details.get('tag_model_number')}")
                logger.warning(f"  Raw TID: {tag_details.get('tid_raw')}")
                
        except Exception as e:
            # Catch errors not handled within identify_tag (e.g., mock transport error)
            logger.exception(f"  Unexpected exception during identification for {epc}: {e}")
            
        print("-" * 20) # Separator

    logger.info("Identification example finished.")


if __name__ == "__main__":
    # Ensure necessary imports are available for the mock responses dict
    from uhf_rfid.protocols.cph import constants as cph_const
    from uhf_rfid.core.exceptions import RFIDError
    asyncio.run(main()) 