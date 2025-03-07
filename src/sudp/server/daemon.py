#!/usr/bin/env python3
"""SUDP server daemon implementation."""

import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Optional

from ..common.daemon import Daemon
from ..common.logging import setup_logging
from ..common.config import create_server_config
from .tcp_server import TCPServer

logger = logging.getLogger(__name__)

class ServerDaemon(Daemon):
    """SUDP server daemon implementation."""
    
    def __init__(
        self,
        config_file: Optional[str] = None,
        pid_dir: Optional[str] = None,
        work_dir: Optional[str] = None
    ) -> None:
        """Initialize the server daemon.
        
        Args:
            config_file: Path to YAML config file
            pid_dir: Directory for PID file
            work_dir: Working directory
        """
        # Use user-local directories by default
        home = Path.home()
        default_pid_dir = home / '.local/var/sudp'
        default_work_dir = home
        default_config = home / '.config/sudp/server.yaml'
        
        super().__init__(
            name="sudpd",
            pid_dir=pid_dir or str(default_pid_dir),
            work_dir=work_dir or str(default_work_dir)
        )
        
        self.config_file = config_file or str(default_config)
        self.server: Optional[TCPServer] = None
    
    async def run(self) -> None:
        """Run the server daemon."""
        # Create configuration
        config = create_server_config(self.config_file)
        
        # Configure logging
        logger = setup_logging(
            log_dir=config.log_dir or str(Path.home() / '.local/var/log/sudp'),
            log_level=getattr(logging, config.log_level.upper()),
            enable_file_logging=config.enable_file_logging,
            enable_console_logging=config.enable_console_logging
        )
        
        try:
            # Create and start server
            self.server = TCPServer(
                host=config.host,
                port=config.port,
                max_clients=config.max_clients
            )
            
            async with self.server:
                logger.info(
                    f"SUDP server daemon running on {config.host}:{config.port}"
                )
                
                # Wait for shutdown signal
                await self._shutdown_event.wait()
                
        except Exception as e:
            logger.error(f"Server daemon failed: {e}")
            raise
    
    async def reload_config(self) -> None:
        """Reload server configuration on SIGHUP."""
        if not self.server:
            return
            
        logger.info("Reloading configuration...")
        try:
            # Create new configuration
            config = create_server_config(self.config_file)
            
            # Stop current server
            await self.server.stop()
            
            # Start new server with updated config
            self.server = TCPServer(
                host=config.host,
                port=config.port,
                max_clients=config.max_clients
            )
            await self.server.start()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def cleanup(self) -> None:
        """Clean up server resources."""
        if self.server and self.server.is_running:
            asyncio.run(self.server.stop())
        super().cleanup()

def main() -> None:
    """Main entry point for the server daemon."""
    parser = argparse.ArgumentParser(description="SUDP server daemon")
    parser.add_argument("command", choices=["start", "stop", "restart", "status"],
                       help="Daemon command (start/stop/restart/status)")
    parser.add_argument("--config-file", help="Path to config file")
    parser.add_argument("--pid-dir", help="Directory for PID file")
    parser.add_argument("--work-dir", help="Working directory")
    parser.add_argument("--foreground", action="store_true",
                       help="Run in foreground (no daemonization)")
    
    args = parser.parse_args()
    
    daemon = ServerDaemon(
        config_file=args.config_file,
        pid_dir=args.pid_dir,
        work_dir=args.work_dir
    )
    
    if args.command == "start":
        if args.foreground:
            # Run in foreground
            daemon.handle_signals()
            with daemon.pid_file_lock():
                try:
                    asyncio.run(daemon.run())
                except Exception as e:
                    logger.error(f"Daemon failed: {e}")
                    sys.exit(1)
        else:
            daemon.start()
    elif args.command == "stop":
        daemon.stop()
    elif args.command == "restart":
        daemon.restart()
    elif args.command == "status":
        daemon.status()

if __name__ == "__main__":
    main() 