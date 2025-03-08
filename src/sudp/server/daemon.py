#!/usr/bin/env python3
"""SUDP server daemon implementation."""

import os
import sys
import asyncio
import logging
import argparse
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml

from ..common.daemon import Daemon
from ..common.logging import setup_logging
from ..common.config import create_server_config, get_instance_config_path, list_instances
from .tcp_server import TCPServer

logger = logging.getLogger(__name__)

class ServerDaemon(Daemon):
    """SUDP server daemon implementation."""
    
    def __init__(
        self,
        instance_name: str = "default",
        config_file: Optional[str] = None,
        pid_dir: Optional[str] = None,
        work_dir: Optional[str] = None,
        config_args: Optional[argparse.Namespace] = None
    ) -> None:
        """Initialize the server daemon.
        
        Args:
            instance_name: Instance name for multi-instance support
            config_file: Path to YAML config file
            pid_dir: Directory for PID file
            work_dir: Working directory
            config_args: Additional configuration arguments
        """
        # Use user-local directories by default
        home = Path.home()
        default_pid_dir = home / '.local/var/sudp' / instance_name
        default_work_dir = home
        
        # Use instance-specific config file if not specified
        if not config_file:
            config_file = str(get_instance_config_path(instance_name))
        
        super().__init__(
            name="sudpd",
            instance_name=instance_name,
            pid_dir=pid_dir or str(default_pid_dir),
            work_dir=work_dir or str(default_work_dir)
        )
        
        self.config_file = config_file
        self.config_args = config_args
        self.server: Optional[TCPServer] = None
        self.instance_metadata: Dict[str, Any] = {}
    
    async def run(self) -> None:
        """Run the server daemon."""
        # Create configuration
        config = create_server_config(self.config_file, self.config_args)
        
        # Configure logging
        log_dir = config.log_dir
        if not log_dir:
            # Use instance-specific log directory
            if self.instance_name == "default":
                log_dir = str(Path.home() / '.local/var/log/sudp')
            else:
                log_dir = str(Path.home() / '.local/var/log/sudp' / self.instance_name)
        
        logger = setup_logging(
            log_dir=log_dir,
            log_level=getattr(logging, config.log_level.upper()),
            enable_file_logging=config.enable_file_logging,
            enable_console_logging=config.enable_console_logging
        )
        
        # If port is 0, find an available port
        port = config.port
        if port == 0:
            port = self.find_available_port(config.host)
            logger.info(f"Automatically selected port {port}")
        
        try:
            # Create and start server
            self.server = TCPServer(
                host=config.host,
                port=port,
                max_clients=config.max_clients
            )
            
            # Save instance metadata
            self.instance_metadata = {
                "host": config.host,
                "port": port,
                "max_clients": config.max_clients,
                "log_dir": log_dir
            }
            self.save_metadata(self.instance_metadata)
            
            async with self.server:
                logger.info(
                    f"SUDP server instance '{self.instance_name}' running on {config.host}:{port}"
                )
                
                # Wait for shutdown signal
                await self._shutdown_event.wait()
                
        except Exception as e:
            logger.error(f"Server daemon failed: {e}")
            raise
    
    def find_available_port(self, host: str, start_port: int = 11223, max_attempts: int = 100) -> int:
        """Find an available port for the server.
        
        Args:
            host: Host to bind to
            start_port: Starting port number
            max_attempts: Maximum number of ports to try
            
        Returns:
            Available port number
            
        Raises:
            RuntimeError: If no available port is found
        """
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port))
                return port
            except OSError:
                continue
                
        raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts - 1}")
    
    async def reload_config(self) -> None:
        """Reload server configuration on SIGHUP."""
        if not self.server:
            return
            
        logger.info("Reloading configuration...")
        try:
            # Create new configuration
            config = create_server_config(self.config_file, self.config_args)
            
            # Stop current server
            await self.server.stop()
            
            # Start new server with updated config
            self.server = TCPServer(
                host=config.host,
                port=config.port,
                max_clients=config.max_clients
            )
            await self.server.start()
            
            # Update instance metadata
            self.instance_metadata = {
                "host": config.host,
                "port": config.port,
                "max_clients": config.max_clients
            }
            self.save_metadata(self.instance_metadata)
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def cleanup(self) -> None:
        """Clean up server resources."""
        if self.server and self.server.is_running:
            asyncio.run(self.server.stop())
        super().cleanup()

def list_server_instances() -> List[Dict[str, Any]]:
    """List all server instances.
    
    Returns:
        List of instance information dictionaries
    """
    instances = []
    
    # First try using the daemon class method
    daemon_instances = Daemon.list_instances("sudpd")
    if daemon_instances:
        return daemon_instances
    
    # Fallback to using ps command
    try:
        import subprocess
        result = subprocess.run(
            ["ps", "aux"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        for line in result.stdout.splitlines():
            if "sudpd start" in line and "/bin/grep" not in line:
                parts = line.split()
                pid = int(parts[1])
                
                # Extract instance name if available
                instance_name = "default"
                for i, part in enumerate(parts):
                    if part == "--instance" and i + 1 < len(parts):
                        instance_name = parts[i + 1]
                        break
                
                # Extract port if available
                port = 11223
                for i, part in enumerate(parts):
                    if part == "--port" and i + 1 < len(parts):
                        try:
                            port = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
                
                instances.append({
                    "instance_name": instance_name,
                    "pid": pid,
                    "running": True,
                    "metadata": {
                        "host": "127.0.0.1",
                        "port": port
                    }
                })
    except Exception as e:
        logger.error(f"Error listing instances using ps: {e}")
    
    return instances

def print_instances_table(instances: List[Dict[str, Any]]) -> None:
    """Print a formatted table of instances.
    
    Args:
        instances: List of instance information dictionaries
    """
    if not instances:
        print("No SUDP server instances found.")
        return
        
    # Print header
    print(f"{'INSTANCE':<15} {'STATUS':<10} {'PID':<8} {'HOST':<15} {'PORT':<6} {'CLIENTS':<8}")
    print("-" * 70)
    
    # Print each instance
    for instance in instances:
        name = instance["instance_name"]
        status = "RUNNING" if instance["running"] else "STOPPED"
        pid = instance["pid"]
        
        # Get metadata
        metadata = instance["metadata"]
        host = metadata.get("host", "unknown")
        port = metadata.get("port", "unknown")
        clients = metadata.get("active_clients", 0)
        
        print(f"{name:<15} {status:<10} {pid:<8} {host:<15} {port:<6} {clients:<8}")

def main() -> None:
    """Main entry point for the server daemon."""
    parser = argparse.ArgumentParser(description="SUDP server daemon")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start server instance")
    start_parser.add_argument("--instance", dest="instance_name", default="default",
                            help="Instance name (default: default)")
    start_parser.add_argument("--config-file", help="Path to config file")
    start_parser.add_argument("--pid-dir", help="Directory for PID file")
    start_parser.add_argument("--work-dir", help="Working directory")
    start_parser.add_argument("--foreground", action="store_true",
                            help="Run in foreground (no daemonization)")
    start_parser.add_argument("--host", help="Host to bind to")
    start_parser.add_argument("--port", type=int, help="Port to listen on (0 for auto)")
    start_parser.add_argument("--max-clients", type=int, help="Maximum number of clients")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop server instance")
    stop_parser.add_argument("--instance", dest="instance_name", default="default",
                           help="Instance name (default: default)")
    stop_parser.add_argument("--pid-dir", help="Directory for PID file")
    
    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart server instance")
    restart_parser.add_argument("--instance", dest="instance_name", default="default",
                              help="Instance name (default: default)")
    restart_parser.add_argument("--config-file", help="Path to config file")
    restart_parser.add_argument("--pid-dir", help="Directory for PID file")
    restart_parser.add_argument("--work-dir", help="Working directory")
    restart_parser.add_argument("--host", help="Host to bind to")
    restart_parser.add_argument("--port", type=int, help="Port to listen on (0 for auto)")
    restart_parser.add_argument("--max-clients", type=int, help="Maximum number of clients")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check server instance status")
    status_parser.add_argument("--instance", dest="instance_name", default="default",
                             help="Instance name (default: default)")
    status_parser.add_argument("--pid-dir", help="Directory for PID file")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all server instances")
    
    args = parser.parse_args()
    
    if args.command == "list":
        # List all instances
        instances = list_server_instances()
        print_instances_table(instances)
        return
    
    if not args.command:
        parser.print_help()
        return
    
    # Create server configuration if starting or restarting
    if args.command in ("start", "restart"):
        # Create a config_args namespace with just the server configuration options
        config_args_dict = {
            "host": getattr(args, "host", None),
            "port": getattr(args, "port", None),
            "max_clients": getattr(args, "max_clients", None),
            "instance_name": getattr(args, "instance_name", "default")
        }
        # Filter out None values
        config_args_dict = {k: v for k, v in config_args_dict.items() if v is not None}
        config_args = argparse.Namespace(**config_args_dict)
    else:
        config_args = None
    
    daemon = ServerDaemon(
        instance_name=getattr(args, "instance_name", "default"),
        config_file=getattr(args, "config_file", None),
        pid_dir=getattr(args, "pid_dir", None),
        work_dir=getattr(args, "work_dir", None),
        config_args=config_args
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