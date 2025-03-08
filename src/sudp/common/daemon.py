#!/usr/bin/env python3
"""Daemon support for SUDP.

This module provides:
- Base daemon class for process management
- PID file handling
- Signal handling
- Daemon state management
- Multi-instance support
"""

import os
import sys
import atexit
import signal
import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Optional, Set, Callable, Coroutine, Any, Dict, List
from contextlib import contextmanager

from .logging import setup_logging

logger = logging.getLogger(__name__)

class Daemon:
    """Base daemon class with process and signal management.
    
    This class provides:
    - Process daemonization
    - PID file management
    - Signal handling (SIGTERM, SIGINT, SIGHUP)
    - Graceful shutdown support
    - Multi-instance support
    """
    
    def __init__(
        self,
        name: str,
        instance_name: str = "default",
        pid_dir: Optional[str] = None,
        umask: int = 0o022,
        work_dir: Optional[str] = None
    ) -> None:
        """Initialize the daemon.
        
        Args:
            name: Daemon name (used for PID file)
            instance_name: Instance name for multi-instance support
            pid_dir: Directory for PID file
            umask: File mode creation mask
            work_dir: Working directory for daemon
        """
        self.name = name
        self.instance_name = instance_name
        self.umask = umask
        
        # Set up working directory
        if work_dir:
            self.work_dir = Path(work_dir)
        else:
            self.work_dir = Path.home()
        
        # Set up PID file path
        if pid_dir:
            self.pid_dir = Path(pid_dir)
        else:
            # Use user-local directory with instance subdirectory
            self.pid_dir = Path.home() / '.local/var/sudp' / instance_name
            self.pid_dir.mkdir(parents=True, exist_ok=True)
        
        # Create instance-specific PID file name
        if instance_name == "default":
            self.pid_file = self.pid_dir / f"{name}.pid"
        else:
            self.pid_file = self.pid_dir / f"{name}_{instance_name}.pid"
            
        self._pid: Optional[int] = None
        
        # Instance metadata file
        self.metadata_file = self.pid_dir / "metadata.json"
        
        # Signal handling
        self._shutdown_event = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()
        
        # Register cleanup handler
        atexit.register(self.cleanup)
    
    @property
    def is_running(self) -> bool:
        """Check if daemon is running by checking PID file."""
        if not self.pid_file.exists():
            return False
            
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
                
            # Check if process exists
            os.kill(pid, 0)
            return True
            
        except (ValueError, ProcessLookupError):
            # Clean up stale PID file
            try:
                self.pid_file.unlink()
            except FileNotFoundError:
                pass
            return False
        except PermissionError:
            # Process exists but we don't have permission to send signals
            # This still means the process is running
            return True
    
    def get_pid(self) -> Optional[int]:
        """Get daemon PID from PID file."""
        if not self.pid_file.exists():
            return None
            
        try:
            with open(self.pid_file) as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    
    def save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save instance metadata to file.
        
        Args:
            metadata: Dictionary of metadata to save
        """
        # Add standard metadata
        metadata.update({
            "instance_name": self.instance_name,
            "pid": os.getpid(),
            "start_time": time.time(),
            "name": self.name
        })
        
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get instance metadata from file.
        
        Returns:
            Dictionary of metadata or empty dict if file doesn't exist
        """
        if not self.metadata_file.exists():
            return {}
            
        try:
            with open(self.metadata_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return {}
    
    @contextmanager
    def pid_file_lock(self):
        """Context manager for PID file handling."""
        # Write PID file
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))
        
        try:
            yield
        finally:
            # Remove PID file
            try:
                self.pid_file.unlink()
            except FileNotFoundError:
                pass
            
            # Remove metadata file
            try:
                self.metadata_file.unlink()
            except FileNotFoundError:
                pass
    
    def daemonize(self) -> None:
        """Daemonize the current process."""
        # Change working directory
        os.chdir(str(self.work_dir))
        os.umask(self.umask)
        
        # Close all file descriptors
        for fd in range(0, 1024):
            try:
                os.close(fd)
            except OSError:
                pass
        
        # Reopen standard file descriptors to /dev/null
        sys.stdin = open(os.devnull, 'r')
        sys.stdout = open(os.devnull, 'a+')
        sys.stderr = open(os.devnull, 'a+')
    
    def handle_signals(self) -> None:
        """Set up signal handlers."""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self.shutdown(sig))
            )
        
        # SIGHUP for config reload (if supported)
        loop.add_signal_handler(
            signal.SIGHUP,
            lambda: asyncio.create_task(self.reload_config())
        )
    
    async def shutdown(self, sig: signal.Signals) -> None:
        """Handle shutdown signal.
        
        Args:
            sig: Signal that triggered shutdown
        """
        logger.info(f"Received signal {sig.name}, shutting down...")
        self._shutdown_event.set()
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Stop the event loop
        loop = asyncio.get_event_loop()
        loop.stop()
    
    async def reload_config(self) -> None:
        """Reload configuration on SIGHUP.
        
        Override this method to implement config reloading.
        """
        logger.info("SIGHUP received, no config reload implemented")
    
    def cleanup(self) -> None:
        """Clean up resources on exit."""
        logger.info(f"Cleaning up {self.name} daemon...")
    
    def create_task(self, coro: Coroutine) -> asyncio.Task:
        """Create a tracked asyncio task.
        
        Args:
            coro: Coroutine to run as task
            
        Returns:
            Created task
        """
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
    
    async def run(self) -> None:
        """Run the daemon process.
        
        Override this method to implement daemon functionality.
        """
        raise NotImplementedError("Subclasses must implement run()")
    
    def start(self) -> None:
        """Start the daemon process."""
        if self.is_running:
            logger.error(f"{self.name} instance '{self.instance_name}' is already running")
            sys.exit(1)
        
        # Daemonize process
        self.daemonize()
        
        # Set up signal handling
        self.handle_signals()
        
        # Run daemon with PID file management
        with self.pid_file_lock():
            try:
                asyncio.run(self.run())
            except Exception as e:
                logger.error(f"Daemon failed: {e}")
                sys.exit(1)
    
    def stop(self) -> None:
        """Stop the daemon process."""
        pid = self.get_pid()
        if not pid:
            logger.error(f"{self.name} instance '{self.instance_name}' is not running")
            return
        
        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(30):  # 3 seconds timeout
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
            else:
                # Force kill if still running
                os.kill(pid, signal.SIGKILL)
                
            logger.info(f"{self.name} instance '{self.instance_name}' stopped")
            
        except ProcessLookupError:
            # Process already gone, just remove PID file
            try:
                self.pid_file.unlink()
            except FileNotFoundError:
                pass
            logger.info(f"{self.name} instance '{self.instance_name}' was not running (stale PID file)")
            
        except PermissionError:
            logger.error(f"No permission to stop {self.name} instance '{self.instance_name}' (PID: {pid})")
    
    def restart(self) -> None:
        """Restart the daemon process."""
        self.stop()
        time.sleep(1)  # Give it a moment to fully stop
        self.start()
    
    def status(self) -> None:
        """Check and print the daemon status."""
        pid = self.get_pid()
        
        if not pid:
            print(f"{self.name} instance '{self.instance_name}' is not running")
            return
            
        try:
            # Check if process exists
            os.kill(pid, 0)
            
            # Get metadata if available
            metadata = self.get_metadata()
            if metadata:
                # Format start time
                start_time = metadata.get("start_time", 0)
                if start_time:
                    uptime = time.time() - start_time
                    hours, remainder = divmod(uptime, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                    print(f"{self.name} instance '{self.instance_name}' is running (PID: {pid}, uptime: {uptime_str})")
                else:
                    print(f"{self.name} instance '{self.instance_name}' is running (PID: {pid})")
                
                # Print additional metadata if available
                for key, value in metadata.items():
                    if key not in ("instance_name", "pid", "start_time", "name"):
                        print(f"  {key}: {value}")
            else:
                print(f"{self.name} instance '{self.instance_name}' is running (PID: {pid})")
                
        except ProcessLookupError:
            # Process not running, clean up PID file
            try:
                self.pid_file.unlink()
            except FileNotFoundError:
                pass
            print(f"{self.name} instance '{self.instance_name}' is not running (stale PID file)")
            
        except PermissionError:
            print(f"{self.name} instance '{self.instance_name}' is running (PID: {pid}), but you don't have permission to check")

    @classmethod
    def list_instances(cls, name: str, base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all instances of this daemon.
        
        Args:
            name: Daemon name
            base_dir: Base directory for PID files
            
        Returns:
            List of instance information dictionaries
        """
        instances = []
        
        # Determine base directory
        if base_dir:
            pid_base_dir = Path(base_dir)
        else:
            pid_base_dir = Path.home() / '.local/var/sudp'
            
        if not pid_base_dir.exists():
            return instances
            
        # Check default instance
        default_pid_file = pid_base_dir / "default" / f"{name}.pid"
        if default_pid_file.exists():
            try:
                with open(default_pid_file) as f:
                    pid = int(f.read().strip())
                    
                # Check if process exists
                try:
                    os.kill(pid, 0)
                    running = True
                except (ProcessLookupError, PermissionError):
                    running = False
                    
                # Get metadata if available
                metadata_file = default_pid_file.parent / "metadata.json"
                metadata = {}
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                    except Exception:
                        pass
                        
                instances.append({
                    "instance_name": "default",
                    "pid": pid,
                    "running": running,
                    "metadata": metadata
                })
            except (ValueError, IOError):
                pass
                
        # Check instance directories
        for instance_dir in pid_base_dir.iterdir():
            if not instance_dir.is_dir() or instance_dir.name == "default":
                continue
                
            # Check for PID file
            pid_file = instance_dir / f"{name}_{instance_dir.name}.pid"
            if not pid_file.exists():
                pid_file = instance_dir / f"{name}.pid"
                if not pid_file.exists():
                    continue
                    
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    
                # Check if process exists
                try:
                    os.kill(pid, 0)
                    running = True
                except (ProcessLookupError, PermissionError):
                    running = False
                    
                # Get metadata if available
                metadata_file = pid_file.parent / "metadata.json"
                metadata = {}
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                    except Exception:
                        pass
                        
                instances.append({
                    "instance_name": instance_dir.name,
                    "pid": pid,
                    "running": running,
                    "metadata": metadata
                })
            except (ValueError, IOError):
                pass
                
        return instances 