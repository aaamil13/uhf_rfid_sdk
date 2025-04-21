# uhf_rfid/transport/mock.py

import asyncio
import logging
from typing import Optional, Any, Dict, List, Tuple, AsyncGenerator
from collections import deque

from uhf_rfid.transport.base import BaseTransport, AsyncDataCallback # Use correct path
from uhf_rfid.core.exceptions import TransportError, ConnectionError # Use correct path

logger = logging.getLogger(__name__)

class MockTransport(BaseTransport):
    """
    A mock transport layer for testing and simulation.

    Simulates connection, disconnection, sending, and receiving data
    without actual hardware interaction. Responses can be queued up
    or generated dynamically.
    """

    def __init__(self, connection_details: Optional[Dict[str, Any]] = None, name: str = "Mock"):
        """
        Initializes the Mock Transport.

        Args:
            connection_details: Not strictly used but kept for interface compatibility.
            name: A name for this mock instance for logging purposes.
        """
        # Provide default empty dict if None
        super().__init__(connection_details if connection_details is not None else {})
        self._name = name
        # Queue for simulating received data frames (bytes)
        self._response_queue: deque[bytes] = deque()
        # Queue for data to be "sent" (can be inspected by tests)
        self._sent_data_queue: deque[bytes] = deque()
        # Event to signal data available for the reader loop
        self._data_available_event = asyncio.Event()
        # Simulate connection delay
        self._connection_delay = 0.05
        # Simulate data arrival delay
        self._receive_delay = 0.01

        logger.info(f"MockTransport '{self._name}' initialized.")

    async def connect(self) -> None:
        """Simulates establishing a connection."""
        async with self._connection_lock: # Ensure atomicity
            if self._connected:
                logger.warning(f"[{self._name}] Already connected.")
                return

            logger.info(f"[{self._name}] Simulating connection...")
            await asyncio.sleep(self._connection_delay) # Simulate network/serial delay

            # In a real scenario, errors might occur here
            # For mock, assume success unless specifically programmed otherwise
            self._connected = True
            logger.info(f"[{self._name}] Mock connection established.")

            # Start the background reader task
            await self._start_reader()

    async def disconnect(self) -> None:
        """Simulates closing the connection."""
        async with self._connection_lock:
            if not self._connected and not (self._reader_task and not self._reader_task.done()):
                 # logger.debug(f"[{self._name}] Already disconnected.") # Can be noisy
                 return

            logger.info(f"[{self._name}] Simulating disconnection...")

            # Stop the reader task first
            await self._stop_reader()

            self._connected = False
            # Clear queues on disconnect? Optional, depends on desired mock behavior.
            # self.clear_send_queue()
            # self.clear_response_queue()
            logger.info(f"[{self._name}] Mock connection closed.")

    async def send(self, data: bytes) -> None:
        """Simulates sending data."""
        if not self.is_connected():
            raise TransportError(f"[{self._name}] Cannot send data: Not connected.")

        logger.debug(f"[{self._name}] Simulating send: {data.hex(' ').upper()}")
        self._sent_data_queue.append(data)
        # In a real scenario, writing might fail (e.g., serial buffer full)
        # Mock assumes success. Add error simulation if needed.

    async def _read_data_loop(self) -> None:
        """Simulates the background task reading data."""
        logger.info(f"[{self._name}] Mock reader loop started.")
        try:
            while self._connected:
                await self._data_available_event.wait() # Wait until data is added

                if not self._connected: # Check connection status after waking up
                    break

                # Process all available data in the queue
                while self._response_queue:
                    data_to_receive = self._response_queue.popleft()
                    logger.debug(f"[{self._name}] Mock reader loop 'receiving': {data_to_receive.hex(' ').upper()}")

                    if self._data_received_callback:
                         # Simulate network delay before delivering data
                        await asyncio.sleep(self._receive_delay)
                        if not self._connected: break # Check again after delay

                        try:
                            # Call the registered callback (Dispatcher._data_received_handler)
                            await self._data_received_callback(data_to_receive)
                        except Exception as e:
                            logger.exception(f"[{self._name}] Error in data received callback: {e}")
                    else:
                         logger.warning(f"[{self._name}] Data received but no callback registered.")

                # Clear the event only after processing all items currently in the queue
                self._data_available_event.clear()

        except asyncio.CancelledError:
            logger.info(f"[{self._name}] Mock reader loop cancelled.")
            # Propagate cancellation if needed, or just exit cleanly
            raise
        except Exception as e:
            logger.exception(f"[{self._name}] Unexpected error in mock reader loop: {e}")
            # Consider setting an error state?
        finally:
             logger.info(f"[{self._name}] Mock reader loop stopped.")


    # --- Mock Control Methods ---

    def add_response(self, response_frame: bytes) -> None:
        """Adds a pre-built frame to the incoming data queue."""
        logger.debug(f"[{self._name}] Adding mock response: {response_frame.hex(' ').upper()}")
        self._response_queue.append(response_frame)
        self._data_available_event.set() # Signal that data is available

    def add_responses(self, response_frames: List[bytes]) -> None:
         """Adds multiple pre-built frames to the incoming data queue."""
         for frame in response_frames:
              logger.debug(f"[{self._name}] Adding mock response: {frame.hex(' ').upper()}")
              self._response_queue.append(frame)
         if response_frames:
              self._data_available_event.set() # Signal that data is available

    def get_sent_data(self) -> Optional[bytes]:
        """Retrieves the oldest 'sent' data frame from the queue (FIFO)."""
        try:
            return self._sent_data_queue.popleft()
        except IndexError:
            return None

    def get_all_sent_data(self) -> List[bytes]:
        """Retrieves and clears all 'sent' data frames."""
        data = list(self._sent_data_queue)
        self._sent_data_queue.clear()
        return data

    def clear_response_queue(self) -> None:
        """Clears any pending responses."""
        logger.debug(f"[{self._name}] Clearing mock response queue ({len(self._response_queue)} items).")
        self._response_queue.clear()
        self._data_available_event.clear() # Reset event as queue is empty

    def clear_send_queue(self) -> None:
         """Clears the record of sent data."""
         logger.debug(f"[{self._name}] Clearing mock sent data queue ({len(self._sent_data_queue)} items).")
         self._sent_data_queue.clear()

    def set_connection_delay(self, delay: float) -> None:
         """Sets the simulated connection delay."""
         self._connection_delay = max(0, delay)

    def set_receive_delay(self, delay: float) -> None:
          """Sets the simulated delay before delivering received data."""
          self._receive_delay = max(0, delay)
