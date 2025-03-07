#!/usr/bin/env python3
"""SUDP server entry point.

This module provides the command-line interface for running the SUDP server.
"""

import asyncio
import argparse
import logging
from pathlib import Path

from .tcp_server import TCPServer
from ..common.logging import setup_logging

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="SUDP Server")
    
    # Server settings
    parser.add_argument("--host", default="127.0.0.1",
                      help="Address to listen on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=11223,
                      help="Port to listen on (default: 11223)")
    parser.add_argument("--max-clients", type=int, default=100,
                      help="Maximum number of concurrent clients (default: 100)")
    
    # Optional settings
    parser.add_argument("--log", action="store_true",
                      help="Enable logging to file")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable debug logging")
    parser.add_argument("--log-dir", type=str,
                      help="Log directory (default: ~/.sudp/logs)")
    
    return parser.parse_args()

async def main() -> None:
    """Run the SUDP server."""
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
        # Create and start the server
        async with TCPServer(
            host=args.host,
            port=args.port,
            max_clients=args.max_clients
        ) as server:
            # Wait for shutdown signal
            logger.info(
                f"SUDP server running on {args.host}:{args.port}"
            )
            
            try:
                # Keep running until interrupted
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
            
            # Get final metrics
            metrics = server.get_metrics()
            logger.info(f"Final metrics: {metrics}")
            
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C 