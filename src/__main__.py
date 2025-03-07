#!/usr/bin/env python3
"""SUDP client entry point.

This module provides the command-line interface for running the SUDP client.
"""

import asyncio
import argparse
import logging
from pathlib import Path

from .client.client import SUDPClient
from .common.logging import setup_logging

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="SUDP Client")
    
    # UDP settings
    parser.add_argument("--udp-host", default="127.0.0.1",
                      help="Local UDP server address (default: 127.0.0.1)")
    parser.add_argument("--udp-port", type=int, default=1234,
                      help="Local UDP server port (default: 1234)")
    
    # TCP settings
    parser.add_argument("--server-host", default="127.0.0.1",
                      help="Remote server address (default: 127.0.0.1)")
    parser.add_argument("--server-port", type=int, default=11223,
                      help="Remote server port (default: 11223)")
    
    # Optional settings
    parser.add_argument("--buffer-size", type=int, default=65507,
                      help="Maximum packet size (default: 65507)")
    parser.add_argument("--log", action="store_true",
                      help="Enable logging to file")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable debug logging")
    parser.add_argument("--log-dir", type=str,
                      help="Log directory (default: ~/.sudp/logs)")
    
    return parser.parse_args()

async def main() -> None:
    """Run the SUDP client."""
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
        # Create and start the client
        async with SUDPClient(
            udp_host=args.udp_host,
            udp_port=args.udp_port,
            server_host=args.server_host,
            server_port=args.server_port,
            buffer_size=args.buffer_size
        ) as client:
            # Wait for shutdown signal
            logger.info(
                f"SUDP client running. Use nc -u {args.udp_host} {args.udp_port} "
                "to connect"
            )
            
            try:
                # Keep running until interrupted
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
            
            # Get final metrics
            metrics = client.get_metrics()
            logger.info(f"Final metrics: {metrics}")
            
    except Exception as e:
        logger.error(f"Client failed: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C 