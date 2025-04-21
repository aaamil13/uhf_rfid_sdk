# doc/examples/cph/08_complex_params.py
"""Example demonstrating getting and setting complex parameter sets.

This script shows how to manage structured parameter sets like
Working Parameters and Transport Parameters.

The general pattern is:
1. Read the current parameter set.
2. Create a new parameter object (dataclass instance) based on the current values,
   modifying only the desired fields.
3. Set the modified parameter object back to the reader.
4. Optionally read back again to verify the change.
5. **Crucially**, restore the original parameters to avoid leaving the reader
   in an unexpected state.

WARNING: Modifying parameters, especially transport or timing related ones,
can affect reader operation or connectivity. Understand the parameter's
meaning before changing it.
"""

import asyncio
import logging

from uhf_rfid.transport.serial_transport import SerialTransport
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import UhfRfidError
# Import the specific parameter dataclasses needed
from uhf_rfid.protocols.cph.parameters import WorkingParams, TransportParams

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change to your serial port

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_complex_param_commands():
    """Connects to the reader and executes get/set for complex parameter sets."""
    transport = SerialTransport(port=SERIAL_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport=transport, protocol=protocol)

    try:
        async with reader:
            logger.info(f"Connected to reader on {SERIAL_PORT}")

            # --- Working Parameters --- 
            try:
                logger.info("--- Managing Working Parameters ---")
                # 1. Get current working parameters
                logger.info("  Getting current working parameters...")
                current_working_params = await reader.get_working_params()
                logger.info(f"  Current Working Params: {current_working_params}") # Dataclass __repr__

                # 2. Modify some parameters
                # Create a new object based on the current ones, modifying only what's needed
                # WARNING: Ensure you understand the meaning of each parameter before changing it!
                new_working_params = WorkingParams(
                    read_duration=current_working_params.read_duration, # Keep original
                    read_interval=50, # Example: Change interval to 50ms
                    sleep_duration=current_working_params.sleep_duration,
                    antenna_select=current_working_params.antenna_select,
                    rf_spectrum=current_working_params.rf_spectrum,
                    drm_enabled=current_working_params.drm_enabled,
                    inventory_mode=1, # Example: Change inventory mode
                    tag_filter_config=current_working_params.tag_filter_config
                    # Ensure all fields from the dataclass are included
                )

                # 3. Set the new parameters
                logger.info(f"  Setting new working parameters: {new_working_params}")
                await reader.set_working_params(new_working_params)
                logger.info("  Set working parameters command sent.")

                # 4. Verify by reading back
                await asyncio.sleep(0.5)
                params_after_set = await reader.get_working_params()
                logger.info(f"  Working Params after setting: {params_after_set}")

                # 5. Restore original parameters (important!) 
                logger.info("  Restoring original working parameters...")
                await reader.set_working_params(current_working_params)
                logger.info("  Original working parameters restored.")

            except UhfRfidError as e:
                logger.error(f"Error managing working parameters: {e}")

            await asyncio.sleep(1)

            # --- Transport Parameters --- 
            # Similar pattern for other complex parameter sets
            try:
                logger.info("--- Managing Transport Parameters ---")
                # 1. Get current transport parameters
                current_transport_params = await reader.get_transport_params()
                logger.info(f"  Current Transport Params: {current_transport_params}")

                # 2. Modify (Example: Change Wiegand settings if applicable)
                #    NOTE: Modifying transport params like baud rate might require
                #          re-establishing the connection with the new settings.
                new_transport_params = TransportParams(
                    com_address = current_transport_params.com_address,
                    baud_rate_code = current_transport_params.baud_rate_code, # Keep same baud for serial
                    wiegand_enabled = True, # Example: Enable Wiegand
                    wiegand_format = 26, # Example: Wiegand 26
                    wiegand_pulse_width_us = 50, # Example value
                    wiegand_pulse_interval_ms = 5 # Example value
                )

                # 3. Set new parameters
                logger.info(f"  Setting new transport parameters: {new_transport_params}")
                await reader.set_transport_params(new_transport_params)
                logger.info("  Set transport parameters command sent.")

                # 4. Verify
                await asyncio.sleep(0.5)
                params_after_set = await reader.get_transport_params()
                logger.info(f"  Transport Params after setting: {params_after_set}")

                # 5. Restore
                logger.info("  Restoring original transport parameters...")
                await reader.set_transport_params(current_transport_params)
                logger.info("  Original transport parameters restored.")

            except UhfRfidError as e:
                logger.error(f"Error managing transport parameters: {e}")

            # Add examples for other parameter sets (ExtParams, AdvanceParams, etc.) following the same pattern:
            # 1. Get current parameters
            # 2. Create a new parameter object, modifying specific fields
            # 3. Set the new parameters
            # 4. Optionally verify by reading back
            # 5. Restore original parameters

            # Example structure for ExtParams:
            # current_ext = await reader.get_ext_params()
            # new_ext = ExtParams(field1=current_ext.field1, field2=new_value, ...)
            # await reader.set_ext_params(new_ext)
            # ... verify ...
            # await reader.set_ext_params(current_ext)

    except UhfRfidError as e:
        logger.error(f"An RFID error occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    logger.info("Starting Complex Parameters Example...")
    asyncio.run(run_complex_param_commands())
    logger.info("Complex Parameters Example finished.") 