#!/usr/bin/env python3
"""Example UDP client that interacts with the echo server.

This script demonstrates the usage of the UDPClient class by
sending messages to the echo server and receiving responses.

Usage:
    python echo_client.py [options]

Options:
    -h, --help          Show this help message
    --host HOST         Server hostname/IP (default: 127.0.0.1)
    --port PORT         Server port (default: 5005)
    --bind-host HOST    Local bind hostname/IP (default: 127.0.0.1)
    --bind-port PORT    Local bind port (default: 0, auto-assign)
    --timeout SECONDS   Receive timeout in seconds (default: 5.0)
    --log              Enable logging to file
    -v, --verbose      Enable debug logging
    --log-dir DIR      Log directory (default: ~/.sudp/logs)
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.client.udp import UDPClient
from src.common.logging import setup_logging

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="UDP Echo Client")
    parser.add_argument("--host", default="127.0.0.1",
                      help="Server hostname/IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5005,
                      help="Server port (default: 5005)")
    parser.add_argument("--bind-host", default="127.0.0.1",
                      help="Local bind hostname/IP (default: 127.0.0.1)")
    parser.add_argument("--bind-port", type=int, default=0,
                      help="Local bind port (default: 0, auto-assign)")
    parser.add_argument("--timeout", type=float, default=5.0,
                      help="Receive timeout in seconds (default: 5.0)")
    parser.add_argument("--log", action="store_true",
                      help="Enable logging to file")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable debug logging")
    parser.add_argument("--log-dir", type=str,
                      help="Log directory (default: ~/.sudp/logs)")
    return parser.parse_args()

async def main():
    """Run the echo client."""
    args = parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(
        log_dir=args.log_dir if args.log_dir else None,
        log_level=log_level,
        enable_file_logging=args.log,
        enable_console_logging=True
    )
    
    async with UDPClient(
        server_host=args.host,
        server_port=args.port,
        bind_host=args.bind_host,
        bind_port=args.bind_port
    ) as client:
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
                    data, addr = await client.receive(timeout=args.timeout)
                    print(f"Server: {data.decode()}", end="")
                except asyncio.TimeoutError:
                    logger.error(f"Server did not respond in {args.timeout}s")
                    
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