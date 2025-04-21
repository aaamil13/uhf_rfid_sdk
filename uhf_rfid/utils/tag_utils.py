# uhf_rfid/utils/tag_utils.py
import logging
import json
import os
from typing import Dict, Any, TYPE_CHECKING, Optional, cast

# Use absolute imports if Reader is needed type checking
if TYPE_CHECKING:
    from uhf_rfid.core.reader import Reader
    # Assuming RFIDError or a more specific error like ReadTagError exists
    from uhf_rfid.core.exceptions import RFIDError

# Import actual constants
from uhf_rfid.protocols.cph import constants as cph_const

logger = logging.getLogger(__name__)

# --- Tag Definitions Cache ---
_tag_definitions: Optional[Dict[str, Any]] = None
_definitions_filepath: str = os.path.join(
    os.path.dirname(__file__), 'tag_definitions.json'
)


def load_tag_definitions(filepath: str = _definitions_filepath) -> Dict[str, Any]:
    """Loads tag definitions from the specified JSON file and caches them."""
    global _tag_definitions
    if _tag_definitions is not None:
        return _tag_definitions

    try:
        with open(filepath, 'r') as f:
            _tag_definitions = json.load(f)
            logger.info(f"Successfully loaded tag definitions from {filepath}")
            # Perform basic validation if needed
            if not isinstance(_tag_definitions, dict) or 'manufacturers' not in _tag_definitions:
                logger.error("Tag definitions JSON is missing 'manufacturers' key.")
                _tag_definitions = {"manufacturers": {}} # Return empty structure
            return _tag_definitions
    except FileNotFoundError:
        logger.warning(f"Tag definitions file not found at {filepath}. Returning empty definitions.")
        _tag_definitions = {"manufacturers": {}}
        return _tag_definitions
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding tag definitions JSON from {filepath}: {e}")
        _tag_definitions = {"manufacturers": {}}
        return _tag_definitions
    except Exception as e:
        logger.exception(f"Unexpected error loading tag definitions from {filepath}: {e}")
        _tag_definitions = {"manufacturers": {}}
        return _tag_definitions


# --- Manufacturer Map (can be removed if names are always taken from JSON) ---
# MANUFACTURER_MAP: Dict[int, str] = { ... }

async def identify_tag(reader: 'Reader', epc: str) -> Dict[str, Any]:
    """
    Attempts to identify tag capabilities by reading TID and looking up in definitions.

    Reads the first words of TID, parses manufacturer and model, then looks up
    details in the tag_definitions.json file.

    Args:
        reader: The Reader instance to use for communication.
        epc: The EPC of the tag to identify.

    Returns:
        A dictionary containing identified information:
        - epc: The EPC of the tag.
        - tid_raw: Raw hex string of the first words of TID read (or None).
        - manufacturer_id: Parsed manufacturer ID (Mask Designer ID) (or None).
        - tag_model_number: Parsed tag model number from TID (or None).
        - tag_info: Dictionary with detailed info from JSON definitions (or None).
        - error: Description of error if identification failed.
    """
    # Load definitions (uses cache after first call)
    definitions = load_tag_definitions()
    manufacturers_data = definitions.get("manufacturers", {})

    result: Dict[str, Any] = {
        "epc": epc,
        "tid_raw": None,
        "manufacturer_id": None,
        # "manufacturer_name": None, # Now part of tag_info
        "tag_model_number": None,
        "tag_info": None, # Will hold detailed info from JSON
        "error": None,
    }

    # --- Read TID Memory ---
    try:
        tid_data = await reader.read_tag(
            epc=epc,
            mem_bank=cph_const.MEM_BANK_TID,
            word_ptr=0,
            word_count=2 # Read enough for ACI, MDID, TMN
        )
        result["tid_raw"] = tid_data.hex()
        logger.debug(f"Successfully read TID for EPC {epc}: {result['tid_raw']}")

        # --- Parse TID Data ---
        if len(tid_data) < 4:
            raise ValueError(f"TID read returned less than 4 bytes ({len(tid_data)})")

        allocation_class_id = tid_data[0]
        if allocation_class_id == 0xE2: # EPC Gen2 ACI
            manufacturer_id = (tid_data[1] << 4) | (tid_data[2] >> 4)
            tag_model_number = ((tid_data[2] & 0x0F) << 8) | tid_data[3]

            result["manufacturer_id"] = manufacturer_id
            result["tag_model_number"] = tag_model_number

            # --- Look up in Definitions ---
            mdid_str = str(manufacturer_id)
            tmn_str = str(tag_model_number)

            manufacturer_info = manufacturers_data.get(mdid_str)
            if manufacturer_info:
                tag_model_info = manufacturer_info.get("models", {}).get(tmn_str)
                if tag_model_info:
                    # Add manufacturer name to the model info for convenience
                    tag_model_info['manufacturer_name'] = manufacturer_info.get('name', 'Unknown')
                    result["tag_info"] = tag_model_info
                    logger.info(f"Found definition for {epc} (MDID:{mdid_str}, TMN:{tmn_str}): {tag_model_info.get('model_name')}")
                else:
                    logger.warning(f"Definition not found for {epc} with MDID {mdid_str} and TMN {tmn_str}.")
                    # Store manufacturer name if known, even if model is not
                    result["tag_info"] = {"manufacturer_name": manufacturer_info.get('name')} 
            else:
                logger.warning(f"Manufacturer definition not found for {epc} with MDID {mdid_str}.")

        else:
            logger.warning(f"Unknown Allocation Class ID ({allocation_class_id:#04x}) in TID for EPC {epc}.")
            result["error"] = f"Unknown TID Allocation Class ID: {allocation_class_id:#04x}"

    except Exception as e:
        logger.warning(f"Failed to read or parse TID for EPC {epc}: {e}")
        result["error"] = f"Failed to read/parse TID: {e}"
        if "tid_raw" in result and result["tid_raw"] is None:
            result["tid_raw"] = None

    return result 