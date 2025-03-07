#!/usr/bin/env python3
"""Simple UDP echo server example.

This script demonstrates the basic usage of the UDPSocket class
by implementing a simple echo server that responds to incoming messages.

Usage:
    python echo_server.py

Then in another terminal:
    nc -u 127.0.0.1 5005

Note: Use IP addresses (127.0.0.1) instead of hostnames (localhost) for consistency
behavior across different systems, especially on macOS.

Type messages in the netcat terminal and they will be echoed back.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.common.socket import UDPSocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def echo_server():
    """Run a UDP echo server."""
    async with UDPSocket("127.0.0.1", 5005) as sock:
        print("Echo server running on 127.0.0.1:5005")
        print("Use 'nc -u 127.0.0.1 5005' to connect")
        print("Note: Using IP address (127.0.0.1) instead of hostname (localhost) for consistency")
        
        while True:
            try:
                # Receive data
                data, addr = await sock.receive()
                message = data.decode().strip()
                print(f"Received from {addr}: {message}")

                # Echo back
                response = f"Echo: {message}".encode()
                await sock.send(response, addr)
                
            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(echo_server())
    except KeyboardInterrupt:
        print("\nServer stopped by user") 