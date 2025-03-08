#!/usr/bin/env python3
"""Client-side TCP client implementation.

This component runs on the client side and:
- Maintains a TCP connection to the server
- Forwards UDP packets received from the local server
- Handles responses from the server
- Provides automatic reconnection and error recovery
"""

import asyncio
import logging
import json
import time
from typing import Optional, Callable, Dict, Any, List

from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics
from ..common.recovery import ConnectionManager, ReliableChannel

logger = setup_logging(enable_file_logging=False)

class TCPClient:
    """TCP client that forwards UDP packets to the server.
    
    This client:
    - Maintains a persistent TCP connection
    - Serializes and forwards UDP packets
    - Handles responses and errors
    - Provides automatic reconnection
    - Ensures reliable packet delivery
    - Provides metrics and logging
    """
    
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 8080,
        packet_handler: Optional[Callable[[UDPPacket], None]] = None,
        max_retries: int = 10,
        reconnect_backoff: float = 1.0,
        max_backoff: float = 60.0,
        ack_timeout: float = 5.0,
        enable_reliable_delivery: bool = True
    ) -> None:
        """Initialize the TCP client.
        
        Args:
            server_host: Remote server address
            server_port: Remote server port
            packet_handler: Callback for handling response packets
            max_retries: Maximum number of connection retries
            reconnect_backoff: Initial backoff time for reconnection in seconds
            max_backoff: Maximum backoff time for reconnection in seconds
            ack_timeout: Timeout for packet acknowledgments in seconds
            enable_reliable_delivery: Whether to enable reliable packet delivery
        """
        self.server_addr = (server_host, server_port)
        self.packet_handler = packet_handler
        self.enable_reliable_delivery = enable_reliable_delivery
        
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.metrics = PerformanceMetrics()
        
        # Create connection manager for automatic reconnection
        self.connection_manager = ConnectionManager(
            connect_func=self._connect_internal,
            max_retries=max_retries,
            initial_backoff=reconnect_backoff,
            max_backoff=max_backoff
        )
        
        # Create reliable channel for packet delivery if enabled
        self.reliable_channel = None
        if enable_reliable_delivery:
            self.reliable_channel = ReliableChannel(
                send_func=self._send_raw,
                ack_timeout=ack_timeout,
                max_retries=max_retries
            )
        
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
    
    async def _connect_internal(self) -> None:
        """Internal connection function used by the connection manager."""
        if self.is_connected:
            return
            
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
        
        # Start reliable channel if enabled
        if self.reliable_channel:
            await self.reliable_channel.start()
    
    @log_performance("tcp_connect")
    async def connect(self) -> bool:
        """Connect to the remote server with automatic retry.
        
        Returns:
            True if connection successful, False otherwise
        """
        return await self.connection_manager.connect()
    
    async def _send_raw(self, data: Dict[str, Any]) -> None:
        """Send raw data to the server.
        
        Args:
            data: Data to send
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to server")
            
        # Send with newline delimiter
        message = json.dumps(data) + '\n'
        self._writer.write(message.encode())
        await self._writer.drain()
        
        # Update metrics
        self.metrics.record('packets_sent', 1)
        self.metrics.record('bytes_sent', len(message))
    
    @log_performance("tcp_send")
    async def send_packet(self, packet: UDPPacket) -> None:
        """Send a UDP packet to the server with reliability guarantees.
        
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
                'dest_port': packet.dest_port,
                'timestamp': time.time()
            }
            
            # Send with reliability if enabled
            if self.reliable_channel:
                packet_id = await self.reliable_channel.send(data)
                logger.debug(f"Sent packet with ID {packet_id}")
            else:
                await self._send_raw(data)
                logger.debug(f"Forwarded {len(packet.payload)} bytes to server")
            
        except Exception as e:
            log_error(logger, e, {
                'packet_size': len(packet.payload),
                'dest_addr': packet.dest_addr
            })
            
            # Handle connection loss
            if isinstance(e, (ConnectionError, ConnectionResetError, BrokenPipeError)):
                logger.warning("Connection lost during send, triggering reconnection")
                self.connection_manager.connection_lost()
                
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
                    self.connection_manager.connection_lost()
                    break
                    
                # Parse the packet
                data = json.loads(line)
                
                # Check for acknowledgment
                if self.reliable_channel and "_ack" in data:
                    packet_id = data["_ack"]
                    self.reliable_channel.acknowledge(packet_id)
                    continue
                
                # Check for metadata
                if "_meta" in data:
                    meta = data.pop("_meta")
                    
                    # Send acknowledgment if required
                    if meta.get("requires_ack") and meta.get("id"):
                        ack_data = {"_ack": meta["id"]}
                        try:
                            await self._send_raw(ack_data)
                        except Exception as e:
                            logger.error(f"Failed to send acknowledgment: {e}")
                
                # Create UDP packet from data
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
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                continue
            except Exception as e:
                log_error(logger, e, {'phase': 'response_handling'})
                
                # Handle connection loss
                if isinstance(e, (ConnectionError, ConnectionResetError, BrokenPipeError)):
                    logger.warning("Connection lost during receive, triggering reconnection")
                    self.connection_manager.connection_lost()
                    break
                    
                continue
    
    async def close(self) -> None:
        """Close the connection."""
        if not self.is_connected:
            return
            
        logger.info("Closing connection to server...")
        self._shutdown_event.set()
        
        # Stop reliable channel if enabled
        if self.reliable_channel:
            await self.reliable_channel.stop()
        
        # Reset connection manager
        self.connection_manager.reset()
        
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
            'uptime': self.metrics.measure_time(),
            'reconnect_attempts': self.connection_manager.retry_count,
            'reliable_delivery': self.enable_reliable_delivery
        })
        
        # Add reliable channel metrics if enabled
        if self.reliable_channel:
            metrics.update({
                'unacknowledged_packets': len(self.reliable_channel.buffer.packets),
                'max_buffer_size': self.reliable_channel.buffer.max_size
            })
            
        return metrics 