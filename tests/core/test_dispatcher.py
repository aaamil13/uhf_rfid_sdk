# tests/core/test_dispatcher.py

import asyncio
import logging

import pytest

from uhf_rfid.core.dispatcher import Dispatcher
from uhf_rfid.core.exceptions import TimeoutError, CommandError
from uhf_rfid.protocols import framing
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.protocols.cph import tlv  # For building responses
from uhf_rfid.protocols.cph.protocol import CPHProtocol
# Fixtures and test data will use these modules
from uhf_rfid.transport.mock import MockTransport


# Make sure pytest-asyncio is installed: pip install pytest-asyncio

# --- Test Fixtures ---

@pytest.fixture
def mock_transport() -> MockTransport:
    """Provides a MockTransport instance."""
    return MockTransport(name="DispatcherTest")

@pytest.fixture
def protocol() -> CPHProtocol:
    """Provides a CPHProtocol instance."""
    return CPHProtocol()

@pytest.fixture
def dispatcher(mock_transport: MockTransport, protocol: CPHProtocol) -> Dispatcher:
    """Provides a Dispatcher instance initialized with mock transport and protocol."""
    # Use a shorter timeout for tests to speed them up
    return Dispatcher(mock_transport, protocol, response_timeout=0.1)

# --- Helper to build simple response frames ---

def build_mock_response(cmd_code: int, params_tlv: bytes = b'', status_code: int = 0x00, address: int = 0x0000) -> bytes:
    """Builds a standard success (or error) response frame."""
    status_tlv_bytes = tlv.build_tlv(cph_const.TAG_STATUS, bytes([status_code]))
    all_params = status_tlv_bytes + params_tlv
    return framing.build_frame(
        frame_type=cph_const.FRAME_TYPE_RESPONSE,
        address=address,
        frame_code=cmd_code,
        parameters=all_params
    )

def build_mock_notification(notif_code: int, params_tlv: bytes, address: int = 0x0000) -> bytes:
    """Builds a notification frame."""
    return framing.build_frame(
        frame_type=cph_const.FRAME_TYPE_NOTIFICATION,
        address=address,
        frame_code=notif_code,
        parameters=params_tlv
    )

# --- Test Cases ---

@pytest.mark.asyncio
async def test_send_command_success(dispatcher: Dispatcher, mock_transport: MockTransport, protocol: CPHProtocol):
    """Test sending a command and receiving a successful response."""
    await mock_transport.connect()

    command_code = 0x40 # Get Version
    # Prepare mock response (Status=OK, Version=4.0.1, DevType=5)
    version_tlv = tlv.build_tlv(cph_const.TAG_SOFTWARE_VERSION, b'\x04\x00\x01')
    devtype_tlv = tlv.build_tlv(cph_const.TAG_DEVICE_TYPE, b'\x05')
    response_frame = build_mock_response(command_code, params_tlv=version_tlv + devtype_tlv, status_code=0x00)

    # Schedule the response *before* sending command
    mock_transport.add_response(response_frame)

    # Send command and wait
    result = await dispatcher.send_command_wait_response(command_code=command_code)

    # Assertions
    # 1. Command was sent correctly
    sent_cmd = mock_transport.get_sent_data()
    expected_sent_cmd = protocol.encode_command(command_code=command_code)
    assert sent_cmd == expected_sent_cmd

    # 2. Result is the parsed parameters dict
    assert isinstance(result, dict)
    assert result.get(cph_const.TAG_STATUS) == 0x00
    assert cph_const.TAG_SOFTWARE_VERSION in result
    assert result[cph_const.TAG_SOFTWARE_VERSION] == {"major": 4, "minor": 0, "revision": 1}
    assert result.get(cph_const.TAG_DEVICE_TYPE) == 5

@pytest.mark.asyncio
async def test_send_command_reader_error(dispatcher: Dispatcher, mock_transport: MockTransport):
    await mock_transport.connect()
    command_code = cph_const.CMD_SET_PARAMETER
    error_status = cph_const.STATUS_PARAMETER_UNSUPPORTED
    # ---> ПОДАЙ INT <---
    param_tlv = tlv.build_power_parameter_tlv(25) # Промени 25.0 на 25
    response_frame = build_mock_response(command_code, status_code=error_status)
    mock_transport.add_response(response_frame)
    with pytest.raises(CommandError) as exc_info:
        await dispatcher.send_command_wait_response(command_code=command_code, params_data=param_tlv)
    assert exc_info.value.status_code == error_status

@pytest.mark.asyncio
async def test_send_command_timeout(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test command timeout when no response is received."""
    await mock_transport.connect()

    command_code = 0x21 # Start Inventory
    # *Don't* add a response to the mock transport

    # Send command and expect TimeoutError
    with pytest.raises(TimeoutError):
        await dispatcher.send_command_wait_response(command_code=command_code)

    # Verify command was still sent
    assert mock_transport.get_sent_data() is not None

@pytest.mark.asyncio
async def test_notification_received(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test receiving a notification and invoking a registered callback."""
    notification_code = 0x80 # Tag Upload
    # Example tag data (EPC only for simplicity)
    epc_value = b'E2001234ABCD'
    epc_tlv = tlv.build_tlv(cph_const.TAG_EPC, epc_value)
    tag_container_tlv = tlv.build_tlv(cph_const.TAG_SINGLE_TAG, epc_tlv)
    notification_frame = build_mock_notification(notification_code, tag_container_tlv)

    callback_called = asyncio.Event()
    received_data = None

    async def notification_callback(frame_type, address, frame_code, params):
        nonlocal received_data
        received_data = (frame_type, address, frame_code, params)
        callback_called.set()
        await asyncio.sleep(0) # Yield control

    await dispatcher.register_notification_callback(notification_code, notification_callback)

    await mock_transport.connect()
    # Simulate receiving the notification
    mock_transport.add_response(notification_frame)

    # Wait for the callback to be called (with a timeout)
    try:
        await asyncio.wait_for(callback_called.wait(), timeout=0.1)
    except asyncio.TimeoutError:
        pytest.fail("Notification callback was not called.")

    # Assert callback received correct data
    assert received_data is not None
    f_type, addr, f_code, params = received_data
    assert f_type == cph_const.FRAME_TYPE_NOTIFICATION
    assert f_code == notification_code
    assert isinstance(params, dict)
    assert cph_const.TAG_SINGLE_TAG in params
    nested_params = params[cph_const.TAG_SINGLE_TAG]
    assert isinstance(nested_params, dict)
    assert nested_params.get(cph_const.TAG_EPC) == epc_value.hex().upper()

@pytest.mark.asyncio
async def test_multiple_notifications_multiple_callbacks(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test multiple notifications invoking multiple callbacks."""
    # Build two different notifications
    notif1_tlv = tlv.build_tlv(cph_const.TAG_SINGLE_TAG, tlv.build_tlv(cph_const.TAG_EPC, b'TAG1'))
    notif1 = build_mock_notification(0x80, notif1_tlv)
    notif2_tlv = tlv.build_tlv(cph_const.TAG_SINGLE_TAG, tlv.build_tlv(cph_const.TAG_EPC, b'TAG2'))
    notif2 = build_mock_notification(0x80, notif2_tlv)

    # Use lists to track calls for each callback
    callback1_calls = []
    callback2_calls = []
    all_calls_done = asyncio.Event()

    async def callback1(ft, a, fc, p):
        callback1_calls.append(p[cph_const.TAG_SINGLE_TAG][cph_const.TAG_EPC])
        if len(callback1_calls) == 2 and len(callback2_calls) == 2: all_calls_done.set()

    async def callback2(ft, a, fc, p):
        callback2_calls.append(p[cph_const.TAG_SINGLE_TAG][cph_const.TAG_EPC])
        if len(callback1_calls) == 2 and len(callback2_calls) == 2: all_calls_done.set()

    await dispatcher.register_notification_callback(0x80, callback1)
    await dispatcher.register_notification_callback(0x80, callback2)

    # Add notifications
    mock_transport.add_responses([notif1, notif2])

    await mock_transport.connect()
    # Wait for both callbacks to process both notifications
    try:
        await asyncio.wait_for(all_calls_done.wait(), timeout=0.2)
    except asyncio.TimeoutError:
        pytest.fail("Not all callbacks received all notifications.")

    # Assertions
    expected_epcs_hex = sorted([b'TAG1'.hex().upper(), b'TAG2'.hex().upper()]) # ['54414731', '54414732']
    assert sorted(callback1_calls) == expected_epcs_hex
    assert sorted(callback2_calls) == expected_epcs_hex

@pytest.mark.asyncio
async def test_unregister_notification_callback(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test that unregistering a callback prevents it from being called."""
    notif_tlv = tlv.build_tlv(cph_const.TAG_SINGLE_TAG, tlv.build_tlv(cph_const.TAG_EPC, b'TAG1'))
    notification_frame = build_mock_notification(0x80, notif_tlv)

    callback_called = False

    async def notification_callback(ft, a, fc, p):
        nonlocal callback_called
        callback_called = True

    await dispatcher.register_notification_callback(0x80, notification_callback)
    await dispatcher.unregister_notification_callback(0x80, notification_callback)

    # Simulate receiving the notification AFTER unregistering
    mock_transport.add_response(notification_frame)
    await asyncio.sleep(0.05) # Give time for potential processing

    # Assert callback was NOT called
    assert not callback_called

@pytest.mark.asyncio
async def test_buffer_processing_fragmented(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test processing a frame received in multiple fragments."""
    command_code = 0x40
    response_frame = build_mock_response(command_code) # Simple status OK response

    # Split the frame into two parts
    split_point = len(response_frame) // 2
    fragment1 = response_frame[:split_point]
    fragment2 = response_frame[split_point:]

    # Add fragments sequentially to the transport's callback handler
    # (which adds to dispatcher buffer)
    await dispatcher._data_received_handler(fragment1)
    # At this point, no complete frame should be parsed yet
    assert len(dispatcher._rx_buffer) == len(fragment1)

    # Add the second fragment - this should trigger parsing
    # Use a future to wait for the response to be processed internally
    response_future = asyncio.Future()
    dispatcher._pending_responses[command_code] = response_future # Manually insert for test

    await dispatcher._data_received_handler(fragment2)

    # Wait for the future to be resolved
    try:
        result = await asyncio.wait_for(response_future, timeout=0.1)
        assert isinstance(result, dict)
        assert result.get(cph_const.TAG_STATUS) == 0x00
        assert len(dispatcher._rx_buffer) == 0 # Buffer consumed
    except asyncio.TimeoutError:
        pytest.fail("Fragmented response was not processed.")

@pytest.mark.asyncio
async def test_buffer_processing_multiple_frames(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test processing multiple frames received in a single chunk."""
    cmd1_code = 0x21
    resp1 = build_mock_response(cmd1_code)
    cmd2_code = 0x23
    resp2 = build_mock_response(cmd2_code)

    # Use futures to track responses
    future1 = asyncio.Future()
    future2 = asyncio.Future()
    dispatcher._pending_responses[cmd1_code] = future1
    dispatcher._pending_responses[cmd2_code] = future2

    # Simulate receiving both frames at once
    await dispatcher._data_received_handler(resp1 + resp2)

    # Wait for both futures
    try:
        result1 = await asyncio.wait_for(future1, timeout=0.1)
        result2 = await asyncio.wait_for(future2, timeout=0.1)
        assert result1.get(cph_const.TAG_STATUS) == 0x00
        assert result2.get(cph_const.TAG_STATUS) == 0x00
        assert len(dispatcher._rx_buffer) == 0 # Buffer consumed
    except asyncio.TimeoutError:
        pytest.fail("Not all frames from single chunk were processed.")

@pytest.mark.asyncio
async def test_unexpected_response(dispatcher: Dispatcher, mock_transport: MockTransport, caplog):
    """Test receiving a response when no command is pending."""
    caplog.set_level(logging.WARNING) # Capture warnings
    response_frame = build_mock_response(cmd_code=0x99) # Some arbitrary code

    # Simulate receiving the unexpected response
    await dispatcher._data_received_handler(response_frame)
    await asyncio.sleep(0.01) # Allow processing time

    # Assert that a warning was logged
    assert "Received unexpected or late response" in caplog.text
    assert "0x99" in caplog.text

@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_cleanup_cancels_pending(dispatcher: Dispatcher, mock_transport: MockTransport):
    """Test that dispatcher cleanup cancels pending response futures."""
    command_code = 0x40
    future = asyncio.Future()
    dispatcher._pending_responses[command_code] = future

    assert not future.cancelled()

    await dispatcher.cleanup()

    # Основната проверка:
    assert future.cancelled()

    # ---> ОГРАДИ ПОТЕНЦИАЛНОТО ХВЪРЛЯНЕ НА ГРЕШКА <---
    # Проверката на съобщението в exception-а е полезна,
    # но може да предизвика CancelledError да излезе необработен.
    # Нека я сложим в pytest.raises.
    with pytest.raises(asyncio.CancelledError) as exc_info:
        # Опит да се вземе резултат ще хвърли CancelledError
        future.result()

    # Провери съобщението в прихванатото изключение
    assert "Dispatcher cleanup" in str(exc_info.value)