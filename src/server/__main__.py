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
from ..common.config import create_server_config

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="SUDP Server")
    
    # Config file
    parser.add_argument("--config-file", type=str,
                      help="Path to YAML configuration file")
    
    # Server settings
    parser.add_argument("--host", default=None,
                      help="Address to listen on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None,
                      help="Port to listen on (default: 11223)")
    parser.add_argument("--max-clients", type=int, default=None,
                      help="Maximum number of concurrent clients (default: 100)")
    
    # Logging settings
    parser.add_argument("--log-dir", type=str, default=None,
                      help="Log directory (default: ~/.sudp/logs)")
    parser.add_argument("--log-level", type=str, default=None,
                      choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                      help="Logging level (default: INFO)")
    parser.add_argument("--enable-file-logging", action="store_true", default=None,
                      help="Enable logging to file")
    parser.add_argument("--disable-console-logging", action="store_false",
                      dest="enable_console_logging", default=None,
                      help="Disable console logging")
    
    return parser.parse_args()

async def main() -> None:
    """Run the SUDP server."""
    args = parse_args()
    
    # Create configuration
    config = create_server_config(args.config_file, args)
    
    # Configure logging
    logger = setup_logging(
        log_dir=config.log_dir,
        log_level=getattr(logging, config.log_level.upper()),
        enable_file_logging=config.enable_file_logging,
        enable_console_logging=config.enable_console_logging
    )
    
    try:
        # Create and start the server
        async with TCPServer(
            host=config.host,
            port=config.port,
            max_clients=config.max_clients
        ) as server:
            # Wait for shutdown signal
            logger.info(
                f"SUDP server running on {config.host}:{config.port}"
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