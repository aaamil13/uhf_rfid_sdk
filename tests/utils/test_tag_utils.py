# tests/utils/test_tag_utils.py
import pytest
import json
import os
from unittest.mock import AsyncMock, patch, mock_open

# Assuming RFIDError is the base exception to mock
from uhf_rfid.core.exceptions import RFIDError
from uhf_rfid.utils import tag_utils

# --- Fixtures ---

@pytest.fixture(autouse=True)
def clear_definitions_cache():
    """Ensure the definitions cache is cleared before each test."""
    tag_utils._tag_definitions = None
    yield
    tag_utils._tag_definitions = None

@pytest.fixture
def mock_reader():
    """Provides a mock Reader object with an AsyncMock for read_tag."""
    reader = AsyncMock()
    reader.read_tag = AsyncMock()
    return reader

# Sample valid definitions for mocking file read
VALID_DEFINITIONS = {
  "manufacturers": {
    "1": { 
      "name": "Impinj", 
      "models": {
        "436": { "model_name": "Monza R6", "memory": {}, "features": [], "notes": ""},
        "437": { "model_name": "Monza R6-P", "memory": {}, "features": [], "notes": ""}
      }
    },
    "2": { 
      "name": "Alien Technology",
      "models": {
         "218": { "model_name": "Higgs 3", "memory": {}, "features": [], "notes": ""}
      }
    }
  }
}

FAKE_EPC = "300000000000000000000001"

# --- Test Cases ---

@pytest.mark.asyncio
async def test_identify_success_found(mock_reader):
    """Test successful identification when tag definition is found."""
    # TID for Impinj (1), Monza R6 (436) -> E2 01 2C 14 (bytes)
    mock_reader.read_tag.return_value = bytes([0xE2, 0x01, 0x2C, 0x14])
    mock_file_content = json.dumps(VALID_DEFINITIONS)
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)) as mock_file, patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    mock_reader.read_tag.assert_awaited_once_with(
        epc=FAKE_EPC, mem_bank=tag_utils.cph_const.MEM_BANK_TID, word_ptr=0, word_count=2
    )
    assert result["error"] is None
    assert result["tid_raw"] == "e2012c14"
    assert result["manufacturer_id"] == 1
    assert result["tag_model_number"] == 436 # 0x1B4 -> 0x2C14 -> Model 436
    assert result["tag_info"] is not None
    assert result["tag_info"]["manufacturer_name"] == "Impinj"
    assert result["tag_info"]["model_name"] == "Monza R6"

@pytest.mark.asyncio
async def test_identify_model_not_found(mock_reader):
    """Test identification when manufacturer is known but model is not."""
    # TID for Impinj (1), Unknown Model (999 = 0x3E7) -> E2 01 3E 7?
    mock_reader.read_tag.return_value = bytes([0xE2, 0x01, 0x3E, 0x70]) # Assuming E70 for lower bits
    mock_file_content = json.dumps(VALID_DEFINITIONS)
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    assert result["error"] is None
    assert result["manufacturer_id"] == 1
    assert result["tag_model_number"] == 999 # (0x3E << 4) | (0x70 >> 4) is wrong. TMN = ((0x3E & 0x0F) << 8) | 0x70 = (0xE << 8) | 0x70 = 0xE70 = 3696. Let's fix TID data to match model 999 = 0x3E7
    # Correct TID for MDID=1, TMN=999 (0x3E7)
    # MDID = 1 (0x001). Byte1=0x00, Byte2[7:4]=0x01 -> 0x00, 0x10
    # TMN = 999 (0x3E7). Byte2[3:0]=0x03, Byte3=0xE7 -> 0x13, 0xE7
    # TID = E2 00 13 E7
    mock_reader.read_tag.return_value = bytes([0xE2, 0x00, 0x13, 0xE7])
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)
        
    assert result["error"] is None
    assert result["manufacturer_id"] == 1 # (0x00 << 4) | (0x13 >> 4) = 1
    assert result["tag_model_number"] == 999 # ((0x13 & 0x0F) << 8) | 0xE7 = (0x3 << 8) | 0xE7 = 0x3E7 = 999
    assert result["tag_info"] is not None
    assert result["tag_info"]["manufacturer_name"] == "Impinj" # Found manufacturer
    assert "model_name" not in result["tag_info"] # Model specific info is missing

@pytest.mark.asyncio
async def test_identify_manufacturer_not_found(mock_reader):
    """Test identification when manufacturer ID is not in definitions."""
    # TID for Unknown Manufacturer (99 = 0x63), Model 1 -> E2 60 3? ?
    # MDID = 99 (0x63) -> Byte1=0x06, Byte2[7:4]=0x03 -> 0x06, 0x30
    # TMN = 1 (0x001) -> Byte2[3:0]=0x00, Byte3=0x01 -> 0x30, 0x01
    # TID = E2 06 30 01
    mock_reader.read_tag.return_value = bytes([0xE2, 0x06, 0x30, 0x01])
    mock_file_content = json.dumps(VALID_DEFINITIONS)

    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    assert result["error"] is None
    assert result["manufacturer_id"] == 99
    assert result["tag_model_number"] == 1
    assert result["tag_info"] is None # Manufacturer not found

@pytest.mark.asyncio
async def test_identify_read_error(mock_reader):
    """Test identification when reader.read_tag raises an error."""
    mock_reader.read_tag.side_effect = RFIDError("Communication timeout")
    mock_file_content = json.dumps(VALID_DEFINITIONS)
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    assert result["error"] == "RFID Error reading TID: Communication timeout"
    assert result["tid_raw"] is None
    assert result["manufacturer_id"] is None
    assert result["tag_model_number"] is None
    assert result["tag_info"] is None

@pytest.mark.asyncio
async def test_identify_invalid_aci(mock_reader):
    """Test identification when TID has an invalid Allocation Class ID."""
    mock_reader.read_tag.return_value = bytes([0xFF, 0x01, 0x2C, 0x14]) # Invalid ACI
    mock_file_content = json.dumps(VALID_DEFINITIONS)
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    assert result["error"] == "Unknown TID Allocation Class ID: 0xff"
    assert result["tid_raw"] == "ff012c14" # Raw data should still be present
    assert result["manufacturer_id"] is None # Parsing skipped
    assert result["tag_model_number"] is None
    assert result["tag_info"] is None

@pytest.mark.asyncio
async def test_identify_short_tid_read(mock_reader):
    """Test identification when TID read returns fewer than 4 bytes."""
    mock_reader.read_tag.return_value = bytes([0xE2, 0x01, 0x2C]) # Only 3 bytes
    mock_file_content = json.dumps(VALID_DEFINITIONS)
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    assert "Error parsing TID data: TID read returned less than expected 4 bytes" in result["error"]
    assert result["tid_raw"] == "e2012c" # Raw data is stored
    assert result["manufacturer_id"] is None
    assert result["tag_model_number"] is None
    assert result["tag_info"] is None

@pytest.mark.asyncio
async def test_identify_definitions_file_not_found(mock_reader):
    """Test identification when the definitions JSON file is missing."""
    mock_reader.read_tag.return_value = bytes([0xE2, 0x01, 0x2C, 0x14]) # Impinj R6
    
    # Simulate FileNotFoundError when opening definitions
    with patch("builtins.open", mock_open()) as mock_file, patch("os.path.dirname", return_value="/fake/dir"):
        mock_file.side_effect = FileNotFoundError
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)
        
    assert result["error"] is None # identify_tag doesn't fail, just returns no info
    assert result["manufacturer_id"] == 1
    assert result["tag_model_number"] == 436
    assert result["tag_info"] is None # No definitions loaded

@pytest.mark.asyncio
async def test_identify_definitions_file_invalid_json(mock_reader):
    """Test identification when the definitions JSON file is corrupted."""
    mock_reader.read_tag.return_value = bytes([0xE2, 0x01, 0x2C, 0x14])
    mock_file_content = "{invalid json" 
    
    with patch("builtins.open", mock_open(read_data=mock_file_content)), patch("os.path.dirname", return_value="/fake/dir"):
        result = await tag_utils.identify_tag(mock_reader, FAKE_EPC)

    assert result["error"] is None
    assert result["manufacturer_id"] == 1
    assert result["tag_model_number"] == 436
    assert result["tag_info"] is None # Definitions failed to load 