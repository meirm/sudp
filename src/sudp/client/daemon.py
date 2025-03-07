#!/usr/bin/env python3
"""SUDP client daemon implementation."""

import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Optional

from ..common.daemon import Daemon
from ..common.logging import setup_logging
from ..common.config import create_client_config
from .client import SUDPClient

logger = logging.getLogger(__name__)

class ClientDaemon(Daemon):
    """SUDP client daemon implementation."""
    
    def __init__(
        self,
        config_file: Optional[str] = None,
        pid_dir: Optional[str] = None,
        work_dir: Optional[str] = None
    ) -> None:
        """Initialize the client daemon.
        
        Args:
            config_file: Path to YAML config file
            pid_dir: Directory for PID file
            work_dir: Working directory
        """
        # Use user-local directories by default
        home = Path.home()
        default_pid_dir = home / '.local/var/sudp'
        default_work_dir = home
        default_config = home / '.config/sudp/client.yaml'
        
        super().__init__(
            name="sudpc",
            pid_dir=pid_dir or str(default_pid_dir),
            work_dir=work_dir or str(default_work_dir)
        )
        
        self.config_file = config_file or str(default_config)
        self.client: Optional[SUDPClient] = None
        
        # Parse command line args for config
        parser = argparse.ArgumentParser(description="SUDP Client Daemon")
        parser.add_argument("--config-file", type=str,
                          help="Path to YAML configuration file")
        self.args = parser.parse_args()
        
        # Config file precedence: constructor > CLI > default
        if not self.config_file:
            self.config_file = self.args.config_file
    
    async def run(self) -> None:
        """Run the client daemon."""
        # Create configuration
        config = create_client_config(self.config_file, self.args)
        
        # Configure logging
        logger = setup_logging(
            log_dir=config.log_dir or str(Path.home() / '.local/var/log/sudp'),
            log_level=getattr(logging, config.log_level.upper()),
            enable_file_logging=config.enable_file_logging,
            enable_console_logging=config.enable_console_logging
        )
        
        try:
            # Create and start client
            self.client = SUDPClient(
                udp_host=config.udp_host,
                udp_port=config.udp_port,
                server_host=config.server_host,
                server_port=config.server_port,
                buffer_size=config.buffer_size
            )
            
            async with self.client:
                logger.info(
                    f"SUDP client daemon running. UDP server on {config.udp_host}:{config.udp_port}"
                )
                
                # Wait for shutdown signal
                await self._shutdown_event.wait()
                
        except Exception as e:
            logger.error(f"Client daemon failed: {e}")
            raise
    
    async def reload_config(self) -> None:
        """Reload client configuration on SIGHUP."""
        if not self.client:
            return
            
        logger.info("Reloading configuration...")
        try:
            # Create new configuration
            config = create_client_config(self.config_file, self.args)
            
            # Stop current client
            await self.client.stop()
            
            # Start new client with updated config
            self.client = SUDPClient(
                udp_host=config.udp_host,
                udp_port=config.udp_port,
                server_host=config.server_host,
                server_port=config.server_port,
                buffer_size=config.buffer_size
            )
            await self.client.start()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def cleanup(self) -> None:
        """Clean up client resources."""
        if self.client and hasattr(self.client, 'is_running') and self.client.is_running:
            asyncio.run(self.client.stop())
        super().cleanup()

def main() -> None:
    """Run the client daemon."""
    daemon = ClientDaemon()
    
    if len(sys.argv) == 2:
        if sys.argv[1] == "start":
            daemon.start()
        elif sys.argv[1] == "stop":
            daemon.stop()
        elif sys.argv[1] == "restart":
            daemon.restart()
        elif sys.argv[1] == "status":
            daemon.status()
        else:
            print("Usage: sudpc {start|stop|restart|status}")
            sys.exit(1)
    else:
        print("Usage: sudpc {start|stop|restart|status}")
        sys.exit(1)

if __name__ == "__main__":
    main() 