#!/usr/bin/env python3
"""Simple UDP echo server example.

This script demonstrates the basic usage of the UDPSocket class
by implementing a simple echo server that responds to incoming messages.

Usage:
    python echo_server.py [options]

Options:
    -h, --help          Show this help message
    --host HOST         Host to bind to (default: 127.0.0.1)
    --port PORT         Port to bind to (default: 5005)
    --log              Enable logging to file
    -v, --verbose      Enable debug logging
    --log-dir DIR      Log directory (default: ~/.sudp/logs)

Note: Use IP addresses (127.0.0.1) instead of hostnames (localhost) for consistency
behavior across different systems, especially on macOS.

Type messages in the netcat terminal and they will be echoed back.
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.common.socket import UDPSocket
from src.common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="UDP Echo Server")
    parser.add_argument("--host", default="127.0.0.1",
                      help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5005,
                      help="Port to bind to (default: 5005)")
    parser.add_argument("--log", action="store_true",
                      help="Enable logging to file")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable debug logging")
    parser.add_argument("--log-dir", type=str,
                      help="Log directory (default: ~/.sudp/logs)")
    return parser.parse_args()

@log_performance("echo_server")
async def echo_server(host: str, port: int, logger: logging.Logger):
    """Run a UDP echo server."""
    async with UDPSocket(host, port) as sock:
        logger.info(f"Echo server running on {host}:{port}")
        logger.info(f"Use 'nc -u {host} {port}' to connect")
        
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

def main():
    """Main entry point."""
    args = parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(
        log_dir=args.log_dir if args.log_dir else None,
        log_level=log_level,
        enable_file_logging=args.log,
        enable_console_logging=True
    )
    
    try:
        asyncio.run(echo_server(args.host, args.port, logger))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")

if __name__ == "__main__":
    main() 