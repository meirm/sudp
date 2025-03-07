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
from .common.config import create_client_config

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="SUDP Client")
    
    # Config file
    parser.add_argument("--config-file", type=str,
                      help="Path to YAML configuration file")
    
    # UDP settings
    parser.add_argument("--udp-host", default=None,
                      help="Local UDP server address (default: 127.0.0.1)")
    parser.add_argument("--udp-port", type=int, default=None,
                      help="Local UDP server port (default: 1234)")
    
    # TCP settings
    parser.add_argument("--server-host", default=None,
                      help="Remote server address (default: 127.0.0.1)")
    parser.add_argument("--server-port", type=int, default=None,
                      help="Remote server port (default: 11223)")
    
    # Optional settings
    parser.add_argument("--buffer-size", type=int, default=None,
                      help="Maximum packet size (default: 65507)")
    
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
    """Run the SUDP client."""
    args = parse_args()
    
    # Create configuration
    config = create_client_config(args.config_file, args)
    
    # Configure logging
    logger = setup_logging(
        log_dir=config.log_dir,
        log_level=getattr(logging, config.log_level.upper()),
        enable_file_logging=config.enable_file_logging,
        enable_console_logging=config.enable_console_logging
    )
    
    try:
        # Create and start the client
        async with SUDPClient(
            udp_host=config.udp_host,
            udp_port=config.udp_port,
            server_host=config.server_host,
            server_port=config.server_port,
            buffer_size=config.buffer_size
        ) as client:
            # Wait for shutdown signal
            logger.info(
                f"SUDP client running. Use nc -u {config.udp_host} {config.udp_port} "
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