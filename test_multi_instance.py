#!/usr/bin/env python3
"""Test script for multi-instance support."""

import asyncio
import argparse
import logging
from pathlib import Path

from src.sudp.server.daemon import ServerDaemon
from src.sudp.common.config import create_server_config
from src.sudp.server.tcp_server import TCPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_instance(instance_name, port):
    """Run a server instance."""
    # Create configuration
    config_args = {
        "port": port,
        "instance_name": instance_name
    }
    config_namespace = argparse.Namespace(**config_args)
    
    # Create daemon
    daemon = ServerDaemon(
        instance_name=instance_name,
        config_file=None
    )
    
    # Create configuration
    config_file = None
    config = create_server_config(config_file, config_namespace)
    
    # Configure logging
    log_dir = Path.home() / '.local/var/log/sudp' / instance_name
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Run daemon
    logger.info(f"Starting instance {instance_name} on port {port}")
    
    try:
        # Create and start server
        server = TCPServer(
            host=config.host,
            port=port,
            max_clients=config.max_clients
        )
        
        # Save instance metadata
        daemon.instance_metadata = {
            "host": config.host,
            "port": port,
            "max_clients": config.max_clients,
            "log_dir": str(log_dir)
        }
        daemon.save_metadata(daemon.instance_metadata)
        
        async with server:
            logger.info(
                f"SUDP server instance '{instance_name}' running on {config.host}:{port}"
            )
            
            # Wait for 30 seconds
            await asyncio.sleep(30)
            
    except Exception as e:
        logger.error(f"Server daemon failed: {e}")
        raise

async def main():
    """Run multiple instances."""
    # Run two instances
    tasks = [
        run_instance("test1", 11224),
        run_instance("test2", 11225)
    ]
    
    # Wait for all instances to complete
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main()) 