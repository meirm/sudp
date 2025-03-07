#!/usr/bin/env python3
"""UDP client implementation.

This module provides a high-level UDP client with:
- Asynchronous operation
- Automatic reconnection
- Performance metrics
- Error handling and logging
"""

import asyncio
from typing import Optional, Tuple, Union
from pathlib import Path

from ..common.socket import UDPSocket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

# Set up logging with only console output by default
logger = setup_logging(enable_file_logging=False)

class UDPClient:
    """High-level UDP client implementation."""
    
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 5005,
        bind_host: str = "127.0.0.1",
        bind_port: int = 0  # Let OS choose port
    ) -> None:
        """Initialize UDP client.
        
        Args:
            server_host: Server hostname/IP
            server_port: Server port
            bind_host: Local bind hostname/IP
            bind_port: Local bind port (0 for auto-assign)
        """
        self.server_addr = (server_host, server_port)
        self.bind_addr = (bind_host, bind_port)
        self.socket: Optional[UDPSocket] = None
        self.metrics = PerformanceMetrics()
        
    async def __aenter__(self) -> 'UDPClient':
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
        
    @log_performance("client_connect")
    async def connect(self) -> None:
        """Connect to the server."""
        if self.socket is not None:
            await self.close()
            
        try:
            self.socket = UDPSocket(self.bind_addr[0], self.bind_addr[1])
            await self.socket.__aenter__()
            logger.info(f"Connected to server at {self.server_addr}")
            self.metrics.record('connected', 1)
            
        except Exception as e:
            log_error(logger, e, {
                'server_addr': self.server_addr,
                'bind_addr': self.bind_addr
            })
            raise
    
    @log_performance("client_send")
    async def send(self, data: Union[str, bytes]) -> None:
        """Send data to the server.
        
        Args:
            data: Data to send (string or bytes)
        """
        if isinstance(data, str):
            data = data.encode()
            
        if self.socket is None:
            await self.connect()
            
        try:
            await self.socket.send(data, self.server_addr)
            self.metrics.record('bytes_sent', len(data))
            logger.debug(f"Sent {len(data)} bytes to {self.server_addr}")
            
        except Exception as e:
            log_error(logger, e, {
                'data_size': len(data),
                'server_addr': self.server_addr
            })
            raise
    
    @log_performance("client_receive")
    async def receive(self, timeout: float = None) -> Tuple[bytes, Tuple[str, int]]:
        """Receive data from the server.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Tuple of (data, address)
        """
        if self.socket is None:
            await self.connect()
            
        try:
            if timeout is not None:
                data, addr = await asyncio.wait_for(
                    self.socket.receive(),
                    timeout=timeout
                )
            else:
                data, addr = await self.socket.receive()
                
            self.metrics.record('bytes_received', len(data))
            logger.debug(f"Received {len(data)} bytes from {addr}")
            return data, addr
            
        except asyncio.TimeoutError:
            logger.warning(f"Receive timeout after {timeout}s")
            raise
            
        except Exception as e:
            log_error(logger, e, {'timeout': timeout})
            raise
    
    async def close(self) -> None:
        """Close the connection."""
        if self.socket is not None:
            await self.socket.__aexit__(None, None, None)
            self.socket = None
            logger.info("Connection closed")
            self.metrics.record('disconnected', 1) 