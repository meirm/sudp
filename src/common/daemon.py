#!/usr/bin/env python3
"""Daemon support for SUDP.

This module provides:
- Base daemon class for process management
- PID file handling
- Signal handling
- Daemon state management
"""

import os
import sys
import atexit
import signal
import asyncio
import logging
from pathlib import Path
from typing import Optional, Set, Callable, Coroutine, Any
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
    """
    
    def __init__(
        self,
        name: str,
        pid_dir: Optional[str] = None,
        umask: int = 0o022,
        work_dir: str = "/"
    ) -> None:
        """Initialize the daemon.
        
        Args:
            name: Daemon name (used for PID file)
            pid_dir: Directory for PID file (default: /var/run or /tmp)
            umask: File mode creation mask
            work_dir: Working directory for daemon
        """
        self.name = name
        self.umask = umask
        self.work_dir = work_dir
        
        # Set up PID file path
        if pid_dir:
            self.pid_dir = Path(pid_dir)
        else:
            # Try standard locations
            self.pid_dir = Path("/var/run")
            if not os.access(self.pid_dir, os.W_OK):
                self.pid_dir = Path("/tmp")
        
        self.pid_file = self.pid_dir / f"{name}.pid"
        self._pid: Optional[int] = None
        
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
            
        except (ValueError, ProcessLookupError, PermissionError):
            return False
    
    def get_pid(self) -> Optional[int]:
        """Get daemon PID from PID file."""
        if not self.pid_file.exists():
            return None
            
        try:
            with open(self.pid_file) as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    
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
    
    def daemonize(self) -> None:
        """Daemonize the current process using double fork."""
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit first parent
        except OSError as e:
            logger.error(f"First fork failed: {e}")
            sys.exit(1)
        
        # Decouple from parent environment
        os.chdir(self.work_dir)
        os.umask(self.umask)
        os.setsid()
        
        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit second parent
        except OSError as e:
            logger.error(f"Second fork failed: {e}")
            sys.exit(1)
        
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
            logger.error(f"{self.name} is already running")
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
            logger.error(f"{self.name} is not running")
            return
        
        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(30):  # 3 seconds timeout
                try:
                    os.kill(pid, 0)
                    asyncio.sleep(0.1)
                except ProcessLookupError:
                    break
            else:
                # Force kill if still running
                os.kill(pid, signal.SIGKILL)
                
        except ProcessLookupError:
            logger.info(f"{self.name} is not running")
        except PermissionError:
            logger.error(f"Permission denied to stop {self.name}")
    
    def restart(self) -> None:
        """Restart the daemon process."""
        self.stop()
        self.start()
    
    def status(self) -> None:
        """Check daemon status."""
        pid = self.get_pid()
        if not pid:
            print(f"{self.name} is not running")
            return
        
        try:
            os.kill(pid, 0)
            print(f"{self.name} is running (PID: {pid})")
        except ProcessLookupError:
            print(f"{self.name} is not running (stale PID file)")
        except PermissionError:
            print(f"{self.name} is running (PID: {pid}), but you don't have permission to check") 