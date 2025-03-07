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
import sys
from pathlib import Path
import logging

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.common.socket import UDPSocket
from src.common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

# Set up logging
logger = setup_logging(log_level=logging.DEBUG)  # Set to DEBUG level

@log_performance("echo_server")
async def echo_server():
    """Run a UDP echo server."""
    async with UDPSocket("127.0.0.1", 5005) as sock:
        logger.info("Echo server running on 127.0.0.1:5005")
        logger.info("Use 'nc -u 127.0.0.1 5005' to connect")
        logger.info("Note: Using IP address (127.0.0.1) instead of hostname (localhost) for consistency")
        
        metrics = PerformanceMetrics()
        message_count = 0
        total_bytes = 0
        
        while True:
            try:
                # Receive data
                logger.debug("Waiting for data...")
                data, addr = await sock.receive()
                message = data.decode().strip()
                message_count += 1
                total_bytes += len(data)
                
                metrics.record('messages_processed', message_count)
                metrics.record('total_bytes_received', total_bytes)
                metrics.record('last_message_size', len(data))
                
                logger.info(f"Received from {addr}: {message}")
                logger.debug(f"Message size: {len(data)} bytes")

                # Echo back
                response = f"Echo: {message}\n".encode()
                logger.debug(f"Sending response of {len(response)} bytes")
                await sock.send(response, addr)
                logger.debug(f"Sent response to {addr}")
                
                total_bytes += len(response)
                metrics.record('total_bytes_sent', total_bytes)
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                metrics.record('uptime', metrics.measure_time())
                break
            except Exception as e:
                log_error(logger, e, {
                    'addr': addr if 'addr' in locals() else None,
                    'messages_processed': message_count,
                    'total_bytes': total_bytes
                })

if __name__ == "__main__":
    try:
        asyncio.run(echo_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user") 