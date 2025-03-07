#!/usr/bin/env python3
"""UDP server implementation.

This module provides a high-level UDP server with:
- Asynchronous operation
- Multiple client connection handling
- Performance metrics
- Error handling and logging
"""

import asyncio
import logging
from typing import Dict, Optional, Set, Tuple, Union

from ..common.socket import UDPSocket
from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

# Set up logging with only console output by default
logger = setup_logging(enable_file_logging=False)

class UDPServer:
    """High-level UDP server implementation.
    
    This server can:
    - Handle multiple client connections
    - Forward packets to specified destinations
    - Track performance metrics
    - Provide detailed logging
    """
    
    def __init__(
        self,
        listen_host: str = "127.0.0.1",
        listen_port: int = 5006,
        forward_host: Optional[str] = None,
        forward_port: Optional[int] = None,
        buffer_size: int = 65507
    ) -> None:
        """Initialize UDP server.
        
        Args:
            listen_host: Address to listen on
            listen_port: Port to listen on
            forward_host: Optional host to forward packets to
            forward_port: Optional port to forward packets to
            buffer_size: Maximum packet size (default: max UDP size)
        """
        self.listen_addr = (listen_host, listen_port)
        self.forward_addr = (forward_host, forward_port) if forward_host and forward_port else None
        self.buffer_size = buffer_size
        
        self.socket: Optional[UDPSocket] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Track active clients
        self.active_clients: Set[Tuple[str, int]] = set()
        
        # Performance metrics
        self.metrics = PerformanceMetrics()
        
        # Packet handlers for different packet types
        self._packet_handlers: Dict[str, callable] = {}
        
    async def __aenter__(self) -> 'UDPServer':
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
    
    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running and self.socket is not None
    
    @log_performance("server_start")
    async def start(self) -> None:
        """Start the UDP server.
        
        Creates the socket and starts listening for incoming packets.
        """
        if self.is_running:
            raise RuntimeError("Server is already running")
            
        try:
            self.socket = UDPSocket(
                self.listen_addr[0],
                self.listen_addr[1],
                self.buffer_size
            )
            await self.socket.__aenter__()
            self._running = True
            self._shutdown_event.clear()
            
            logger.info(
                f"UDP server listening on {self.listen_addr[0]}:{self.listen_addr[1]}"
                + (f", forwarding to {self.forward_addr[0]}:{self.forward_addr[1]}"
                   if self.forward_addr else "")
            )
            
            self.metrics.record('server_start_time', self.metrics.measure_time())
            
            # Start the main server loop
            await self._server_loop()
            
        except Exception as e:
            log_error(logger, e, {
                'listen_addr': self.listen_addr,
                'forward_addr': self.forward_addr
            })
            await self.stop()
            raise
    
    @log_performance("server_loop")
    async def _server_loop(self) -> None:
        """Main server loop handling incoming packets."""
        while not self._shutdown_event.is_set():
            try:
                if not self.socket:
                    break
                    
                # Receive next packet
                data, addr = await self.socket.receive()
                
                # Track new clients
                if addr not in self.active_clients:
                    self.active_clients.add(addr)
                    logger.info(f"New client connection from {addr}")
                    self.metrics.record('active_clients', len(self.active_clients))
                
                # Process the packet
                await self._handle_packet(data, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(logger, e, {'phase': 'packet_processing'})
                continue
    
    @log_performance("packet_handling")
    async def _handle_packet(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle an incoming packet.
        
        Args:
            data: Raw packet data
            addr: Source address tuple (host, port)
        """
        try:
            # Create packet object
            packet = UDPPacket(
                payload=data,
                source_addr=addr[0],
                source_port=addr[1],
                dest_addr=self.forward_addr[0] if self.forward_addr else None,
                dest_port=self.forward_addr[1] if self.forward_addr else None
            )
            
            # Update metrics
            self.metrics.record('packets_received', 1)
            self.metrics.record('bytes_received', len(data))
            
            # Forward the packet if destination is configured
            if self.forward_addr and self.socket:
                await self.socket.send(packet)
                self.metrics.record('packets_forwarded', 1)
                self.metrics.record('bytes_forwarded', len(data))
                logger.debug(
                    f"Forwarded {len(data)} bytes from {addr} to "
                    f"{self.forward_addr}"
                )
            
            # Handle based on packet type if handlers exist
            packet_type = packet.get_type() if hasattr(packet, 'get_type') else None
            if packet_type and packet_type in self._packet_handlers:
                await self._packet_handlers[packet_type](packet)
            
        except Exception as e:
            log_error(logger, e, {
                'source_addr': addr,
                'data_size': len(data),
                'forward_addr': self.forward_addr
            })
    
    async def stop(self) -> None:
        """Stop the server and cleanup resources."""
        if not self.is_running:
            return
            
        logger.info("Shutting down UDP server...")
        self._shutdown_event.set()
        
        # Close all client connections
        self.active_clients.clear()
        
        # Stop the socket
        if self.socket:
            await self.socket.__aexit__(None, None, None)
            self.socket = None
        
        self._running = False
        self.metrics.record('server_stop_time', self.metrics.measure_time())
        logger.info("UDP server stopped")
    
    def register_handler(self, packet_type: str, handler: callable) -> None:
        """Register a handler for specific packet types.
        
        Args:
            packet_type: Type of packet to handle
            handler: Async function to handle the packet
        """
        self._packet_handlers[packet_type] = handler
        logger.debug(f"Registered handler for packet type: {packet_type}")
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current server metrics.
        
        Returns:
            Dictionary of metrics including:
            - active_clients: Number of connected clients
            - uptime: Server uptime in seconds
            - packets_received: Total packets received
            - bytes_received: Total bytes received
            - packets_forwarded: Total packets forwarded
            - bytes_forwarded: Total bytes forwarded
        """
        metrics = self.metrics.metrics.copy()
        metrics.update({
            'active_clients': len(self.active_clients),
            'uptime': self.metrics.measure_time()
        })
        return metrics 