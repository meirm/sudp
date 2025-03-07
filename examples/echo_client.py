#!/usr/bin/env python3
"""Example UDP client that interacts with the echo server.

This script demonstrates the usage of the UDPClient class by
sending messages to the echo server and receiving responses.

Usage:
    python echo_client.py

The client will connect to the echo server at 127.0.0.1:5005
and allow you to type messages that will be echoed back.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.client.udp import UDPClient
from src.common.logging import setup_logging

# Set up logging
logger = setup_logging()

async def main():
    """Run the echo client."""
    async with UDPClient() as client:  # Defaults to 127.0.0.1:5005
        logger.info("Echo client started. Type messages and press Enter.")
        logger.info("Press Ctrl+C to exit.")
        
        while True:
            try:
                # Get user input
                message = await asyncio.get_event_loop().run_in_executor(
                    None, input, "> "
                )
                
                # Send to server
                await client.send(message)
                
                # Receive response with timeout
                try:
                    data, addr = await client.receive(timeout=5.0)
                    print(f"Server: {data.decode()}", end="")
                except asyncio.TimeoutError:
                    logger.error("Server did not respond in time")
                    
            except KeyboardInterrupt:
                logger.info("Client stopped by user")
                break
            except EOFError:  # Handle Ctrl+D
                logger.info("Input stream closed")
                break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C 