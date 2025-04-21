# Troubleshooting

This page lists common issues encountered when using the `uhf_rfid` library and provides guidance on how to resolve them.

## Connection Issues

**Error:** `ConnectionRefusedError`, `TimeoutError` (during connection), `SerialException` (e.g., port not found)

**Possible Causes & Solutions:**

*   **Physical Connection:**
    *   Ensure the reader is powered on.
    *   Check that the USB or Ethernet cable is securely connected at both ends.
    *   Try a different USB port or Ethernet cable.
*   **Serial Port Configuration (`SerialTransport`):**
    *   **Correct Port Name:** Verify the serial port name (`port` argument) is correct for your operating system (e.g., `"COM3"` on Windows, `"/dev/ttyUSB0"` on Linux). Check Device Manager (Windows) or `dmesg | grep tty` / `ls /dev/tty*` (Linux) to identify the correct port.
    *   **Permissions (Linux):** Ensure your user has permission to access the serial port. You might need to add your user to the `dialout` or `tty` group: `sudo usermod -a -G dialout $USER` (log out and back in afterward).
    *   **Baud Rate:** Double-check that the `baudrate` specified matches the reader's configured baud rate. If unsure, try common values like `115200` or `9600`.
    *   **Driver:** Make sure the correct driver for your USB-to-Serial adapter (e.g., CH340, FTDI) is installed.
    *   **Port Busy:** Ensure no other application is currently using the serial port.
*   **Network Configuration (`TcpTransport`):**
    *   **Correct IP Address/Hostname:** Verify the `host` argument points to the reader's correct IP address.
    *   **Correct Port Number:** Ensure the `port` argument matches the TCP port the reader is listening on (e.g., `6000`).
    *   **Network Connectivity:** Ping the reader's IP address from your computer to confirm basic network reachability.
    *   **Firewall:** Check if a firewall on your computer, the reader, or the network is blocking the connection on the specified TCP port. Temporarily disabling firewalls can help diagnose this.
    *   **Reader Network Settings:** Confirm the reader's own network configuration (IP address, subnet mask, gateway, listening port) is correct.

## Communication Errors

**Error:** `TimeoutError` (during command execution), `ChecksumError`, `FrameParseError`, `ProtocolError`

**Possible Causes & Solutions:**

*   **Reader Responsiveness:**
    *   The reader might be busy, unresponsive, or in an unexpected state. Try power cycling the reader.
    *   If the error occurs during long operations or on a noisy channel, consider increasing the `timeout` value in the transport configuration, although this usually masks underlying issues.
*   **Incorrect Protocol/Framing:**
    *   Ensure you are using the correct protocol implementation (`CphProtocol`) for your reader model.
    *   These errors often indicate data corruption during transmission.
*   **Serial Noise:**
    *   For serial connections, electrical noise can corrupt data. Use shielded cables, keep them away from power lines, and ensure proper grounding.
*   **Tag Issues:**
    *   If the error occurs during tag operations (`read_tag_memory`, `write_tag_memory`), ensure a tag is within range and responsive.
    *   The specific tag might be faulty or unsupported.
*   **Firmware Bugs:** Less commonly, the reader's firmware might have bugs. Check for firmware updates from the manufacturer.

## Command Execution Errors

**Error:** `CommandError` (often wraps a specific status code from the reader)

**Possible Causes & Solutions:**

*   **Check the Error Status:** The `CommandError` exception often contains a status code indicating the reason for failure. Access it via `error.status_code` and potentially a message via `error.get_status_message()` (if available for that code).
    ```python
    from uhf_rfid import CommandError

    try:
        await reader.some_command(...)
    except CommandError as e:
        print(f"Command failed with status code: {e.status_code}")
        # You might need a mapping from status code to meaning
        # print(f"Status message: {e.get_status_message()}")
    ```
*   **Invalid Parameters:** Ensure the parameters passed to the command method (e.g., power level, memory bank, address, data) are valid according to the reader's specifications and the library's requirements.
*   **Reader State:** Some commands might only be valid in certain reader states (e.g., you might not be able to change some settings while an inventory is running).
*   **Tag Not Present/Accessible:** Operations requiring a specific tag (like writing memory) will fail if the tag is not present, not selected, or has moved out of range.
*   **Memory Lock Status:** Trying to write to a locked memory bank on a tag will result in an error.
*   **Permissions/Access Password:** Some tag operations might require an access password which is not currently implemented in this library's high-level write commands.

## Parameter Issues (`ExtParams`, `WorkingParams`, etc.)

**Error:** `ValueError` (during packing/unpacking), unexpected reader behavior after setting parameters.

**Possible Causes & Solutions:**

*   **Invalid Values:** Ensure the values assigned to parameter dataclass fields are within the expected ranges and types.
*   **Speculative Formats:** As noted in `parameters.md`, the packing formats for `WorkingParams`, `TransportParams`, and especially `AdvanceParams` are **speculative**. Setting incorrect values, particularly in `AdvanceParams`, could lead to unpredictable behavior or require a factory reset. **Modify these with extreme caution and verify behavior carefully.**
*   **Read Before Write:** It's often a good practice to read the current parameters (`get_working_params`, etc.) before modifying and writing them back (`set_working_params`). This ensures you only change the intended fields.

## Debugging Tips

*   **Logging:** Enable logging to see the raw communication between the library and the reader. This is invaluable for diagnosing protocol-level issues.
    ```python
    import logging

    logging.basicConfig(level=logging.DEBUG) # Show all messages
    # Or more specific:
    # logging.getLogger("uhf_rfid.transport").setLevel(logging.DEBUG)
    # logging.getLogger("uhf_rfid.protocol").setLevel(logging.DEBUG)
    ```
*   **Isolate the Problem:** Simplify your code to the smallest possible example that reproduces the error.
*   **Check Examples:** Refer to the provided example scripts (`examples/`) to see known-working configurations and command sequences.
*   **Consult Reader Manual:** The reader's official documentation is the ultimate reference for command behavior, status codes, and parameter ranges. 