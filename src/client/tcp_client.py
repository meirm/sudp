#!/usr/bin/env python3
"""Client-side TCP client implementation.

This component runs on the client side and:
- Maintains a TCP connection to the server
- Forwards UDP packets received from the local server
- Handles responses from the server
"""

import asyncio
import logging
import json
from typing import Optional, Callable, Dict, Any

from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

logger = setup_logging(enable_file_logging=False)

class TCPClient:
    """TCP client that forwards UDP packets to the server.
    
    This client:
    - Maintains a persistent TCP connection
    - Serializes and forwards UDP packets
    - Handles responses and errors
    - Provides metrics and logging
    """
    
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 8080,
        packet_handler: Optional[Callable[[UDPPacket], None]] = None
    ) -> None:
        """Initialize the TCP client.
        
        Args:
            server_host: Remote server address
            server_port: Remote server port
            packet_handler: Callback for handling response packets
        """
        self.server_addr = (server_host, server_port)
        self.packet_handler = packet_handler
        
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.metrics = PerformanceMetrics()
        
    async def __aenter__(self) -> 'TCPClient':
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to the server."""
        return (self._reader is not None and 
                self._writer is not None and 
                not self._writer.is_closing())
    
    @log_performance("tcp_connect")
    async def connect(self) -> None:
        """Connect to the remote server."""
        if self.is_connected:
            return
            
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.server_addr[0],
                self.server_addr[1]
            )
            self._running = True
            self._shutdown_event.clear()
            
            logger.info(f"Connected to server at {self.server_addr[0]}:{self.server_addr[1]}")
            self.metrics.record('connected', 1)
            
            # Start response handler
            asyncio.create_task(self._handle_responses())
            
        except Exception as e:
            log_error(logger, e, {'server_addr': self.server_addr})
            await self.close()
            raise
    
    @log_performance("tcp_send")
    async def send_packet(self, packet: UDPPacket) -> None:
        """Send a UDP packet to the server.
        
        Args:
            packet: The UDP packet to forward
        """
        if not self.is_connected:
            await self.connect()
            
        try:
            # Serialize the packet
            data = {
                'payload': packet.payload.hex(),
                'source_addr': packet.source_addr,
                'source_port': packet.source_port,
                'dest_addr': packet.dest_addr,
                'dest_port': packet.dest_port
            }
            
            # Send with newline delimiter
            message = json.dumps(data) + '\n'
            self._writer.write(message.encode())
            await self._writer.drain()
            
            # Update metrics
            self.metrics.record('packets_sent', 1)
            self.metrics.record('bytes_sent', len(packet.payload))
            logger.debug(f"Forwarded {len(packet.payload)} bytes to server")
            
        except Exception as e:
            log_error(logger, e, {
                'packet_size': len(packet.payload),
                'dest_addr': packet.dest_addr
            })
            await self.close()
            raise
    
    @log_performance("tcp_receive")
    async def _handle_responses(self) -> None:
        """Handle response packets from the server."""
        while not self._shutdown_event.is_set():
            try:
                if not self._reader:
                    break
                    
                # Read line-delimited JSON
                line = await self._reader.readline()
                if not line:  # EOF
                    logger.info("Server closed connection")
                    break
                    
                # Parse the packet
                data = json.loads(line)
                packet = UDPPacket(
                    payload=bytes.fromhex(data['payload']),
                    source_addr=data['source_addr'],
                    source_port=data['source_port'],
                    dest_addr=data['dest_addr'],
                    dest_port=data['dest_port']
                )
                
                # Update metrics
                self.metrics.record('packets_received', 1)
                self.metrics.record('bytes_received', len(packet.payload))
                logger.debug(f"Received {len(packet.payload)} bytes from server")
                
                # Forward to handler if set
                if self.packet_handler:
                    await self.packet_handler(packet)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(logger, e, {'phase': 'response_handling'})
                continue
    
    async def close(self) -> None:
        """Close the connection."""
        if not self.is_connected:
            return
            
        logger.info("Closing connection to server...")
        self._shutdown_event.set()
        
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            
        self._reader = None
        self._writer = None
        self._running = False
        
        self.metrics.record('disconnected', 1)
        logger.info("Connection closed")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current client metrics."""
        metrics = self.metrics.metrics.copy()
        metrics.update({
            'connected': self.is_connected,
            'uptime': self.metrics.measure_time()
        })
        return metrics 