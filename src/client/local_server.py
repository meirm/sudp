#!/usr/bin/env python3
"""Client-side UDP server implementation.

This component runs on the client side and:
- Listens for UDP packets from local applications
- Forwards them to the TCP client for secure transmission
"""

import asyncio
import logging
from typing import Optional, Tuple, Callable

from ..common.socket import UDPSocket
from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

logger = setup_logging(enable_file_logging=False)

class LocalUDPServer:
    """UDP server that runs on the client side.
    
    This server:
    - Listens for UDP packets from local applications
    - Forwards them to a TCP client for secure transmission
    - Tracks metrics and provides logging
    """
    
    def __init__(
        self,
        listen_host: str = "127.0.0.1",
        listen_port: int = 5005,
        buffer_size: int = 65507,
        packet_handler: Optional[Callable[[UDPPacket], None]] = None
    ) -> None:
        """Initialize the local UDP server.
        
        Args:
            listen_host: Local address to listen on
            listen_port: Local port to listen on
            buffer_size: Maximum packet size
            packet_handler: Callback for handling received packets
        """
        self.listen_addr = (listen_host, listen_port)
        self.buffer_size = buffer_size
        self.packet_handler = packet_handler
        
        self.socket: Optional[UDPSocket] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.metrics = PerformanceMetrics()
        
    async def __aenter__(self) -> 'LocalUDPServer':
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
    
    @log_performance("local_server_start")
    async def start(self) -> None:
        """Start the UDP server."""
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
            
            logger.info(f"Local UDP server listening on {self.listen_addr[0]}:{self.listen_addr[1]}")
            self.metrics.record('server_start_time', self.metrics.measure_time())
            
            # Start the main server loop
            await self._server_loop()
            
        except Exception as e:
            log_error(logger, e, {'listen_addr': self.listen_addr})
            await self.stop()
            raise
    
    async def _send_ack(self, addr: Tuple[str, int], message: str = None) -> None:
        """Send acknowledgment to a client.
        
        Args:
            addr: Client address tuple (host, port)
            message: Optional custom message
        """
        if not message:
            message = "Packet received, forwarding to server...\n"
            
        try:
            if self.socket:
                ack_packet = UDPPacket(
                    payload=message.encode(),
                    source_addr=self.listen_addr[0],
                    source_port=self.listen_addr[1],
                    dest_addr=addr[0],
                    dest_port=addr[1]
                )
                await self.socket.send(ack_packet)
                self.metrics.record('acks_sent', 1)
                logger.debug(f"Sent ack to {addr}: {message}")
                
        except Exception as e:
            log_error(logger, e, {
                'addr': addr,
                'message': message
            })
    
    @log_performance("local_server_loop")
    async def _server_loop(self) -> None:
        """Main server loop handling incoming packets."""
        while not self._shutdown_event.is_set():
            try:
                if not self.socket:
                    break
                    
                # Receive next packet
                data, addr = await self.socket.receive()
                
                # Create packet object
                packet = UDPPacket(
                    payload=data,
                    source_addr=addr[0],
                    source_port=addr[1],
                    dest_addr=None,  # Will be set by the TCP client
                    dest_port=None
                )
                
                # Update metrics
                self.metrics.record('packets_received', 1)
                self.metrics.record('bytes_received', len(data))
                logger.debug(f"Received {len(data)} bytes from {addr}")
                
                # Send acknowledgment
                await self._send_ack(addr)
                
                # Forward to handler if set
                if self.packet_handler:
                    await self.packet_handler(packet)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(logger, e, {'phase': 'packet_processing'})
                continue
    
    async def send_response(self, packet: UDPPacket) -> None:
        """Send a response back to a local client.
        
        Args:
            packet: Packet to send back
        """
        if not self.is_running or not self.socket:
            raise RuntimeError("Server is not running")
            
        try:
            # Format the response
            if isinstance(packet.payload, bytes):
                try:
                    # Try to decode and format the response
                    message = f"Echo: {packet.payload.decode().strip()}\n"
                    packet.payload = message.encode()
                except UnicodeDecodeError:
                    # If we can't decode, just forward as is
                    pass
            
            await self.socket.send(packet)
            self.metrics.record('packets_sent', 1)
            self.metrics.record('bytes_sent', len(packet.payload))
            logger.debug(f"Sent {len(packet.payload)} bytes to {packet.dest_addr}:{packet.dest_port}")
            
        except Exception as e:
            log_error(logger, e, {
                'dest_addr': packet.dest_addr,
                'dest_port': packet.dest_port,
                'payload_size': len(packet.payload)
            })
            raise
    
    async def stop(self) -> None:
        """Stop the server."""
        if not self.is_running:
            return
            
        logger.info("Shutting down local UDP server...")
        self._shutdown_event.set()
        
        if self.socket:
            await self.socket.__aexit__(None, None, None)
            self.socket = None
        
        self._running = False
        self.metrics.record('server_stop_time', self.metrics.measure_time())
        logger.info("Local UDP server stopped")
    
    def get_metrics(self) -> dict:
        """Get current server metrics."""
        metrics = self.metrics.metrics.copy()
        metrics.update({
            'uptime': self.metrics.measure_time(),
            'acks_sent': self.metrics.metrics.get('acks_sent', 0)
        })
        return metrics 