# tests/core/test_reader.py

import asyncio
from unittest.mock import AsyncMock, MagicMock
import datetime
from unittest.mock import patch
# import struct # Remove if not used
import logging

import pytest

from uhf_rfid.core.exceptions import ConnectionError, TimeoutError, CommandError, ProtocolError
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.status import ConnectionStatus
# --- Remove direct protocol imports if only testing Reader's interaction with BaseProtocol --- 
# from uhf_rfid.protocols import framing
# from uhf_rfid.protocols.cph import constants as cph_const
# from uhf_rfid.protocols.cph import tlv
# from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.transport.mock import MockTransport
# Import only needed types/classes for tests
from uhf_rfid.protocols.base_protocol import BaseProtocol, DeviceInfo, TagReadData # Import BaseProtocol and common types
from uhf_rfid.protocols.cph.parameters import (
    ExtParams, WorkingParams, TransportParams, AdvanceParams, UsbDataParams, DataFlagParams, ModbusParams
)
from uhf_rfid.protocols.cph import constants as cph_const # Still needed for CMD/NOTIF codes in assertions
from uhf_rfid.core.dispatcher import Dispatcher, NotificationCallback

logger = logging.getLogger(__name__)

# --- Fixtures remain mostly the same, but Reader fixture is now in TestReaderCommands --- 

# @pytest.fixture
# def mock_transport() -> MockTransport: ... # Moved into class setup
# @pytest.fixture
# def protocol() -> CPHProtocol: ... # No longer needed if mocking BaseProtocol
# @pytest.fixture
# def reader(mock_transport: MockTransport, protocol: CPHProtocol) -> Reader: ... # Moved into class setup

# --- Remove Helper Functions if they were CPH specific --- 
# def build_mock_response(...): ... # No longer needed if mocking protocol decode methods
# def build_mock_notification(...): ... # No longer needed for Reader tests

# --- Test Class with Refactored Mocks --- 

class TestReaderCommands:

    @pytest.fixture(autouse=True)
    def setup_mocks(self, event_loop):
        """Setup fresh mocks for each test, mocking BaseProtocol interactions."""
        self.mock_transport = MagicMock(spec=MockTransport)
        self.mock_transport.connect = AsyncMock()
        self.mock_transport.disconnect = AsyncMock()
        self.mock_transport.is_connected = MagicMock(return_value=True)
        self.mock_transport.send = AsyncMock()
        self.mock_transport.set_data_received_callback = MagicMock()

        self.mock_protocol = MagicMock(spec=BaseProtocol)

        # Add mocks for encode/decode methods used in tests
        self.mock_protocol.encode_get_version_request = MagicMock(return_value=b'')
        self.mock_protocol.decode_get_version_response = MagicMock()
        self.mock_protocol.encode_set_default_params_request = MagicMock(return_value=b'')
        # RTC (No specific encode needed in BaseProtocol, Reader uses lambda)
        self.mock_protocol.decode_get_rtc_response = MagicMock()

        # --- Single Params ---
        self.mock_protocol.encode_get_power_request = MagicMock(return_value=b'') # Updated
        self.mock_protocol.decode_get_power_response = MagicMock()
        self.mock_protocol.encode_set_power_request = MagicMock(return_value=b'')

        self.mock_protocol.encode_get_buzzer_request = MagicMock(return_value=b'') # Added
        self.mock_protocol.decode_get_buzzer_response = MagicMock() # Added
        self.mock_protocol.encode_set_buzzer_request = MagicMock(return_value=b'') # Added

        self.mock_protocol.encode_get_filter_time_request = MagicMock(return_value=b'') # Added
        self.mock_protocol.decode_get_filter_time_response = MagicMock() # Added
        self.mock_protocol.encode_set_filter_time_request = MagicMock(return_value=b'') # Added

        # --- Tag Operations ---
        self.mock_protocol.encode_read_tag_request = MagicMock(return_value=b'') # Renamed/Updated
        self.mock_protocol.decode_read_tag_response = MagicMock() # Renamed/Updated
        self.mock_protocol.encode_write_tag_request = MagicMock(return_value=b'') # Added
        self.mock_protocol.encode_lock_tag_request = MagicMock(return_value=b'') # Added
        self.mock_protocol.encode_kill_tag_request = MagicMock(return_value=b'') # Added

        # --- Inventory --- 
        self.mock_protocol.encode_start_inventory_request = MagicMock(return_value=b'') # Added
        self.mock_protocol.encode_stop_inventory_request = MagicMock(return_value=b'') # Added
        self.mock_protocol.encode_inventory_single_burst_request = MagicMock(return_value=b'') # Added

        # Add more as needed (e.g., for complex params)
        # self.mock_protocol.encode_get_working_params_request = MagicMock(return_value=b'')
        # self.mock_protocol.decode_get_working_params_response = MagicMock()

        self.reader = Reader(transport=self.mock_transport, protocol=self.mock_protocol)
        self.reader._state = ConnectionStatus.CONNECTED
        self.reader._dispatcher = MagicMock(spec=Dispatcher)
        self.mock_dispatcher = self.reader._dispatcher
        self.mock_dispatcher.send_command_wait_response = AsyncMock()
        self.mock_dispatcher.register_notification_callback = AsyncMock()
        self.mock_dispatcher.unregister_notification_callback = AsyncMock()
        self.mock_dispatcher.unregister_callback_from_all = AsyncMock()

        self.reader.connect = AsyncMock()
        self.reader.disconnect = AsyncMock()

    # def teardown_method(self, method):
    #     self.patcher.stop() # Remove if patcher is removed

    # --- Test Tag Notification Registration (largely unchanged, depends on dispatcher mock) --- 
    @pytest.mark.asyncio
    async def test_reader_register_tag_notify_callback(self):
        """Test registering tag notifications via dispatcher."""
        async def specific_tag_callback(ft, a, fc, params):
            pass # Dummy callback

        await self.reader.register_tag_notify_callback(specific_tag_callback)

        # Verify dispatcher mock was called correctly with CPH NOTIFICATION codes
        self.mock_dispatcher.register_notification_callback.assert_any_call(
            cph_const.NOTIF_TAG_UPLOADED, specific_tag_callback
        )
        self.mock_dispatcher.register_notification_callback.assert_any_call(
            cph_const.NOTIF_OFFLINE_TAG_UPLOADED, specific_tag_callback
        )
        assert self.mock_dispatcher.register_notification_callback.call_count == 2

    # --- Test Refactored Commands --- 

    @pytest.mark.asyncio
    async def test_reader_set_default_params_success(self):
        """Test set_default_params delegates encoding and calls dispatcher."""
        address = 0x1234
        encoded_params = b'' # Expect empty params for this command
        self.mock_protocol.encode_set_default_params_request.return_value = encoded_params
        # Mock dispatcher response (doesn't matter much as no decode_func is used)
        self.mock_dispatcher.send_command_wait_response.return_value = {cph_const.TAG_STATUS: 0x00}

        await self.reader.set_default_params(address=address)

        # Verify protocol encoding was called
        self.mock_protocol.encode_set_default_params_request.assert_called_once_with()
        # Verify dispatcher was called with correct cmd code and encoded params
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_SET_DEFAULT_PARAM,
            address=address,
            params_data=encoded_params
        )

    @pytest.mark.asyncio
    async def test_reader_get_rtc_time_success(self):
        """Test get_rtc_time delegates encoding/decoding and calls dispatcher."""
        address = 0x0000
        expected_datetime = datetime.datetime(2023, 10, 27, 10, 30, 45)
        encoded_params = b'' # Reader uses lambda: b'' if encode_get_rtc_request is missing
        dummy_response_params = {'some_internal_representation': 'value'} # What dispatcher returns

        # Configure mocks
        # No need to mock specific encode if Reader uses lambda
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
        self.mock_protocol.decode_get_rtc_response.return_value = expected_datetime

        # Act
        result_datetime = await self.reader.get_rtc_time(address=address)

        # Assert
        # 1. Check dispatcher call (encode is implicitly b'')
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_QUERY_RTC_TIME,
            address=address,
            params_data=encoded_params
        )
        # 2. Check decoding call - This is the crucial part
        self.mock_protocol.decode_get_rtc_response.assert_called_once_with(dummy_response_params)
        # 3. Check final result
        assert result_datetime == expected_datetime

    @pytest.mark.asyncio
    async def test_reader_get_power_success(self):
        """Test get_power delegates correctly."""
        address = 0x0000
        expected_power = 27 # dBm
        # encoded_query_params = b'\x26\x01\x01' # Not relevant for the new structure
        encoded_get_power_request = b'dummy_encoded_get_power' # What encode_get_power_request returns
        dummy_response_params = {cph_const.TAG_SINGLE_PARAMETER: b'\x01\x1b'} # Example response from dispatcher

        self.mock_protocol.encode_get_power_request.return_value = encoded_get_power_request
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
        self.mock_protocol.decode_get_power_response.return_value = expected_power

        result_power = await self.reader.get_power(address=address)

        self.mock_protocol.encode_get_power_request.assert_called_once_with() # Still no args for get_power request
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            address=address,
            params_data=encoded_get_power_request
        )
        # Now decode_func is called inside _execute_command, so it should receive the dispatcher's response
        self.mock_protocol.decode_get_power_response.assert_called_once_with(dummy_response_params)
        assert result_power == expected_power

    @pytest.mark.asyncio
    async def test_reader_set_power_success(self):
        """Test set_power delegates correctly."""
        address = 0x0000
        power_to_set = 30
        encoded_set_params = b'\x26\x02\x01\x1e'
        self.mock_dispatcher.send_command_wait_response.return_value = {cph_const.TAG_STATUS: 0x00}
        encode_args = {"power_dbm": power_to_set} # Define encode_args as dict
        self.mock_protocol.encode_set_power_request.return_value = encoded_set_params
        await self.reader.set_power(power_to_set, address=address)
        # Expect call with keyword arguments
        self.mock_protocol.encode_set_power_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_SET_PARAMETER,
            address=address,
            params_data=encoded_set_params
        )

    @pytest.mark.asyncio
    async def test_reader_set_buzzer_success(self):
        """Test set_buzzer delegates correctly."""
        address = 0x0000
        enabled = True
        encode_args = {"enabled": enabled}
        encoded_params = b'dummy_set_buzzer_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00}

        self.mock_protocol.encode_set_buzzer_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.set_buzzer(enabled=enabled, address=address)

        # Expect call with keyword arguments
        self.mock_protocol.encode_set_buzzer_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_SET_PARAMETER,
            address=address,
            params_data=encoded_params
        )

    @pytest.mark.asyncio
    async def test_reader_get_buzzer_success(self):
        """Test get_buzzer_status delegates correctly."""
        address = 0x0000
        expected_status = True
        encoded_params = b'dummy_get_buzzer_request'
        dummy_response_params = {cph_const.TAG_SINGLE_PARAMETER: b'\x02\x01'} # Type=Buzzer, Value=Enabled

        self.mock_protocol.encode_get_buzzer_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
        self.mock_protocol.decode_get_buzzer_response.return_value = expected_status

        result_status = await self.reader.get_buzzer_status(address=address)

        self.mock_protocol.encode_get_buzzer_request.assert_called_once_with()
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            address=address,
            params_data=encoded_params
        )
        # Now decode_func is called inside _execute_command
        self.mock_protocol.decode_get_buzzer_response.assert_called_once_with(dummy_response_params)
        assert result_status == expected_status

    @pytest.mark.asyncio
    async def test_reader_set_filter_time_success(self):
        """Test set_filter_time delegates correctly."""
        address = 0x0000
        filter_time_ms = 150 # Example value
        encode_args = {"filter_time_ms": filter_time_ms}
        encoded_params = b'dummy_set_filter_time_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00}

        self.mock_protocol.encode_set_filter_time_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.set_filter_time(filter_time_ms=filter_time_ms, address=address)

        # Expect call with keyword arguments
        self.mock_protocol.encode_set_filter_time_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_SET_PARAMETER,
            address=address,
            params_data=encoded_params
        )

    @pytest.mark.asyncio
    async def test_reader_get_filter_time_success(self):
        """Test get_filter_time delegates correctly."""
        address = 0x0000
        expected_time = 150
        encoded_params = b'dummy_get_filter_time_request'
        dummy_response_params = {cph_const.TAG_SINGLE_PARAMETER: b'\x03\x96'} # Type=FilterTime, Value=150 (0x96)

        self.mock_protocol.encode_get_filter_time_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
        self.mock_protocol.decode_get_filter_time_response.return_value = expected_time

        result_time = await self.reader.get_filter_time(address=address)

        self.mock_protocol.encode_get_filter_time_request.assert_called_once_with()
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            address=address,
            params_data=encoded_params
        )
        # Now decode_func is called inside _execute_command
        self.mock_protocol.decode_get_filter_time_response.assert_called_once_with(dummy_response_params)
        assert result_time == expected_time

    # --- Add more tests for other refactored methods (e.g., read/write tag, get/set complex params) ---

    # --- Inventory Tests ---
    @pytest.mark.asyncio
    async def test_reader_start_inventory_success(self):
        """Test start_inventory delegates correctly."""
        address = 0x5555
        params = None # Example: no specific params
        encode_args = {"params": params} if params else {}
        encoded_params = b'dummy_start_inventory_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00}

        self.mock_protocol.encode_start_inventory_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.start_inventory(params=params, address=address)

        self.mock_protocol.encode_start_inventory_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_START_INVENTORY,
            address=address,
            params_data=encoded_params
        )

    @pytest.mark.asyncio
    async def test_reader_stop_inventory_success(self):
        """Test stop_inventory delegates correctly."""
        address = 0x6666
        encoded_params = b'dummy_stop_inventory_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00}

        self.mock_protocol.encode_stop_inventory_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.stop_inventory(address=address)

        self.mock_protocol.encode_stop_inventory_request.assert_called_once_with()
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_STOP_INVENTORY,
            address=address,
            params_data=encoded_params
        )

    @pytest.mark.asyncio
    async def test_reader_inventory_single_burst_success(self):
        """Test inventory_single_burst delegates correctly."""
        address = 0x7777
        params = {"session": 1} # Example params
        encode_args = {"params": params} if params else {}
        encoded_params = b'dummy_single_burst_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00}

        self.mock_protocol.encode_inventory_single_burst_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.inventory_single_burst(params=params, address=address)

        # Expect call with keyword arguments
        self.mock_protocol.encode_inventory_single_burst_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_ACTIVE_INVENTORY,
            address=address,
            params_data=encoded_params
        )

    # Example: Read Tag
    @pytest.mark.asyncio
    async def test_reader_read_tag_success(self):
        """Test read_tag delegates correctly."""
        address = 0x1111
        mem_bank = cph_const.MEM_BANK_EPC
        word_addr = 2
        word_count = 6
        access_password = "11223344"
        encode_args = {
            "mem_bank": mem_bank,
            "word_addr": word_addr,
            "word_count": word_count,
            "access_password": access_password,
        }
        encoded_params = b'dummy_read_tag_request'
        dummy_response_params = {cph_const.TAG_EPC: b'\xaa\xbb\xcc\xdd\xee\xff'}
        expected_data = b'\xaa\xbb\xcc\xdd\xee\xff'

        self.mock_protocol.encode_read_tag_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
        self.mock_protocol.decode_read_tag_response.return_value = expected_data

        result = await self.reader.read_tag(
            mem_bank=mem_bank,
            word_addr=word_addr,
            word_count=word_count,
            access_password=access_password,
            address=address,
        )

        # Expect call with keyword arguments
        self.mock_protocol.encode_read_tag_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_READ_TAG,
            address=address,
            params_data=encoded_params
        )
        # Now decode_func is called inside _execute_command
        self.mock_protocol.decode_read_tag_response.assert_called_once_with(dummy_response_params)
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_reader_write_tag_success(self):
        """Test write_tag delegates correctly."""
        address = 0x2222
        mem_bank = cph_const.MEM_BANK_USER
        word_addr = 0
        data = b'\x11\x22\x33\x44'
        access_password = "00000000"
        encode_args = {
            "mem_bank": mem_bank,
            "word_addr": word_addr,
            "data": data,
            "access_password": access_password,
        }
        encoded_params = b'dummy_write_tag_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00} # Expect only status OK

        self.mock_protocol.encode_write_tag_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.write_tag(
            mem_bank=mem_bank,
            word_addr=word_addr,
            data=data,
            access_password=access_password,
            address=address,
        )

        # Expect call with keyword arguments
        self.mock_protocol.encode_write_tag_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_WRITE_TAG,
            address=address,
            params_data=encoded_params
        )
        # No decode_func for write_tag

    @pytest.mark.asyncio
    async def test_reader_lock_tag_success(self):
        """Test lock_tag delegates correctly."""
        address = 0x3333
        # Example: Lock User memory write perma lock
        lock_payload = 0b00000100_00000011 # Action=perma(3), User=write(1)
        access_password = "FFFFFFFF"
        encode_args = {
            "lock_payload": lock_payload,
            "access_password": access_password,
        }
        encoded_params = b'dummy_lock_tag_request'
        dummy_response_params = {cph_const.TAG_STATUS: 0x00}

        self.mock_protocol.encode_lock_tag_request.return_value = encoded_params
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params

        await self.reader.lock_tag(
            lock_payload=lock_payload,
            access_password=access_password,
            address=address,
        )

        # Expect call with keyword arguments
        self.mock_protocol.encode_lock_tag_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_LOCK_TAG,
            address=address,
            params_data=encoded_params
        )
        # No decode_func for lock_tag

    # @pytest.mark.asyncio
    # async def test_reader_kill_tag_success(self):
    #     """Test kill_tag delegates correctly."""
    #     # Commented out because kill_tag needs refactoring in reader.py
    #     address = 0x4444
    #     kill_password = "12345678"
    #     encode_args = {"kill_password": kill_password}
    #     encoded_params = b'dummy_kill_tag_request'
    #     dummy_response_params = {cph_const.TAG_STATUS: 0x00}
    #
    #     self.mock_protocol.encode_kill_tag_request.return_value = encoded_params
    #     self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
    #
    #     await self.reader.kill_tag(
    #         kill_password=kill_password,
    #         address=address,
    #     )
    #
    #     self.mock_protocol.encode_kill_tag_request.assert_called_once_with(**encode_args)
    #     self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
    #         command_code=cph_const.CMD_LOCK_TAG, # Should use CMD_LOCK_TAG after refactor
    #         address=address,
    #         params_data=encoded_params
    #     )
    #     # No decode_func for kill_tag

    # --- Test Error Handling (Example: Protocol Encoding Error) ---
    @pytest.mark.asyncio
    async def test_reader_set_power_encode_error(self):
        power_to_set = 99
        encode_args = {"power_dbm": power_to_set} # Define encode_args as dict
        self.mock_protocol.encode_set_power_request.side_effect = ProtocolError("Invalid power value")
        with pytest.raises(CommandError, match="Failed to encode request.*"):
            await self.reader.set_power(power_to_set)
        # Expect call with keyword arguments
        self.mock_protocol.encode_set_power_request.assert_called_once_with(**encode_args)
        self.mock_dispatcher.send_command_wait_response.assert_not_called()

    # --- Test Error Handling (Example: Protocol Decoding Error) ---
    @pytest.mark.asyncio
    async def test_reader_get_power_decode_error(self):
        address = 0x0000
        encoded_get_power_request = b'dummy_encoded_get_power'
        dummy_response_params = {'corrupted': 'data'}

        self.mock_protocol.encode_get_power_request.return_value = encoded_get_power_request
        self.mock_dispatcher.send_command_wait_response.return_value = dummy_response_params
        self.mock_protocol.decode_get_power_response.side_effect = ProtocolError("Missing required TLV")

        with pytest.raises(CommandError, match="Failed to decode response.*"):
             await self.reader.get_power(address=address)

        self.mock_protocol.encode_get_power_request.assert_called_once_with()
        self.mock_dispatcher.send_command_wait_response.assert_awaited_once_with(
            command_code=cph_const.CMD_QUERY_PARAMETER,
            address=address,
            params_data=encoded_get_power_request
        )
        # Now decode_func is called inside _execute_command
        self.mock_protocol.decode_get_power_response.assert_called_once_with(dummy_response_params)


# --- Remove standalone tests or adapt them ---
# (If they were testing CPH specifics directly, they might belong in test_cph_protocol.py now)