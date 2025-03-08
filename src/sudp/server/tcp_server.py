#!/usr/bin/env python3
"""Server-side TCP server implementation.

This component:
- Accepts TCP connections from clients
- Handles JSON-formatted UDP packets
- Echoes packets back for testing
"""

import asyncio
import logging
import json
import time
from typing import Optional, Dict, Set, Any, List, Tuple
from dataclasses import dataclass, field

from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

logger = setup_logging(enable_file_logging=False)

@dataclass
class ClientInfo:
    """Information about a connected client."""
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    client_id: str
    connected_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    packets_received: int = 0
    packets_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    
    @property
    def address(self) -> Tuple[str, int]:
        """Get client address as (host, port) tuple."""
        addr = self.writer.get_extra_info('peername')
        if addr:
            return addr
        return ('unknown', 0)
    
    @property
    def uptime(self) -> float:
        """Get client connection uptime in seconds."""
        return time.time() - self.connected_at
    
    @property
    def idle_time(self) -> float:
        """Get client idle time in seconds."""
        return time.time() - self.last_active
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert client info to dictionary."""
        host, port = self.address
        return {
            "client_id": self.client_id,
            "host": host,
            "port": port,
            "connected_at": self.connected_at,
            "last_active": self.last_active,
            "uptime": self.uptime,
            "idle_time": self.idle_time,
            "packets_received": self.packets_received,
            "packets_sent": self.packets_sent,
            "bytes_received": self.bytes_received,
            "bytes_sent": self.bytes_sent
        }

class TCPServer:
    """TCP server that handles UDP packet forwarding.
    
    This server:
    - Accepts TCP connections from SUDP clients
    - Processes JSON-formatted UDP packets
    - Maintains connection state and metrics
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11223,
        max_clients: int = 100
    ) -> None:
        """Initialize the TCP server.
        
        Args:
            host: Address to listen on
            port: Port to listen on
            max_clients: Maximum number of concurrent clients
        """
        self.host = host
        self.port = port
        self.max_clients = max_clients
        
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Track active clients
        self._clients: Dict[str, ClientInfo] = {}
        self._client_tasks: Dict[str, asyncio.Task] = {}
        
        # Performance metrics
        self.metrics = PerformanceMetrics()
        self._start_time = 0.0
        self._total_connections = 0
        self._total_packets_received = 0
        self._total_packets_sent = 0
        self._total_bytes_received = 0
        self._total_bytes_sent = 0
        self._connection_errors = 0
        self._packet_errors = 0
    
    async def __aenter__(self) -> 'TCPServer':
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
    
    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running and self._server is not None
    
    @property
    def active_clients(self) -> int:
        """Get number of active clients."""
        return len(self._clients)
    
    @property
    def uptime(self) -> float:
        """Get server uptime in seconds."""
        if self._start_time == 0:
            return 0
        return time.time() - self._start_time
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get server metrics.
        
        Returns:
            Dictionary of server metrics
        """
        metrics = self.metrics.metrics.copy()
        metrics.update({
            'active_clients': self.active_clients,
            'uptime': self.uptime
        })
        metrics.update({
            "total_connections": self._total_connections,
            "total_packets_received": self._total_packets_received,
            "total_packets_sent": self._total_packets_sent,
            "total_bytes_received": self._total_bytes_received,
            "total_bytes_sent": self._total_bytes_sent,
            "connection_errors": self._connection_errors,
            "packet_errors": self._packet_errors
        })
        return metrics
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a client.
        
        Args:
            client_id: Client ID
            
        Returns:
            Client information dictionary or None if client not found
        """
        client = self._clients.get(client_id)
        if client:
            return client.to_dict()
        return None
    
    def get_all_clients(self) -> List[Dict[str, Any]]:
        """Get information about all clients.
        
        Returns:
            List of client information dictionaries
        """
        return [client.to_dict() for client in self._clients.values()]
    
    @log_performance("server_start")
    async def start(self) -> None:
        """Start the TCP server."""
        if self.is_running:
            raise RuntimeError("Server is already running")
        
        try:
            self._start_time = time.time()
            self._server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port
            )
            self._running = True
            self._shutdown_event.clear()
            
            logger.info(f"TCP server listening on {self.host}:{self.port}")
            self.metrics.record('server_start_time', self.metrics.measure_time())
            
            # Start serving
            asyncio.create_task(self._server.serve_forever())
            
        except Exception as e:
            log_error(logger, e, {
                'host': self.host,
                'port': self.port
            })
            await self.stop()
            raise
    
    @log_performance("client_handler")
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection.
        
        Args:
            reader: Stream reader for receiving data
            writer: Stream writer for sending data
        """
        peer = writer.get_extra_info('peername')
        logger.info(f"New client connection from {peer}")
        
        if len(self._clients) >= self.max_clients:
            logger.warning(f"Max clients ({self.max_clients}) reached, rejecting {peer}")
            writer.close()
            await writer.wait_closed()
            return
        
        # Get client address
        addr = peer
        client_id = f"{addr[0]}:{addr[1]}" if addr else "unknown"
        
        # Create client info
        client = ClientInfo(
            reader=reader,
            writer=writer,
            client_id=client_id
        )
        
        # Add client
        self._clients[client_id] = client
        self._total_connections += 1
        
        logger.info(f"Client connected: {client_id}")
        
        # Create task for handling client
        task = asyncio.create_task(self._client_loop(client))
        self._client_tasks[client_id] = task
        
        # Wait for task to complete
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Client task cancelled: {client_id}")
        except Exception as e:
            logger.error(f"Error in client task {client_id}: {e}")
            self._connection_errors += 1
        finally:
            # Remove client
            self._clients.pop(client_id, None)
            self._client_tasks.pop(client_id, None)
            
            # Close connection if still open
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
                
            logger.info(f"Client disconnected: {client_id}")
    
    async def _client_loop(self, client: ClientInfo) -> None:
        """Handle client communication loop.
        
        Args:
            client: Client information
        """
        # Track consecutive errors for connection health monitoring
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while not self._shutdown_event.is_set():
            try:
                # Read data
                data = await asyncio.wait_for(client.reader.readline(), timeout=30.0)
                if not data:
                    # Connection closed
                    logger.info(f"Client {client.client_id} closed connection")
                    break
                    
                # Reset error counter on successful read
                consecutive_errors = 0
                    
                # Update client stats
                client.last_active = time.time()
                client.bytes_received += len(data)
                client.packets_received += 1
                self._total_bytes_received += len(data)
                self._total_packets_received += 1
                
                # Process data
                response = await self._process_packet(data.decode().strip())
                
                # Send response if needed
                if response:
                    response_data = (response + '\n').encode()
                    client.writer.write(response_data)
                    await client.writer.drain()
                    
                    # Update client stats
                    client.bytes_sent += len(response_data)
                    client.packets_sent += 1
                    self._total_bytes_sent += len(response_data)
                    self._total_packets_sent += 1
                    
            except asyncio.TimeoutError:
                # No data received within timeout, send heartbeat
                logger.debug(f"No data from client {client.client_id} for 30s, sending heartbeat")
                try:
                    heartbeat = json.dumps({
                        "heartbeat": int(time.time()),
                        "_meta": {
                            "id": f"heartbeat:{int(time.time())}",
                            "timestamp": time.time(),
                            "requires_ack": True
                        }
                    }) + '\n'
                    client.writer.write(heartbeat.encode())
                    await client.writer.drain()
                except Exception as e:
                    logger.error(f"Failed to send heartbeat to {client.client_id}: {e}")
                    consecutive_errors += 1
                    
            except asyncio.CancelledError:
                # Task cancelled
                raise
                
            except Exception as e:
                logger.error(f"Error handling client {client.client_id}: {e}")
                self._packet_errors += 1
                consecutive_errors += 1
                
                # Check if we should disconnect due to too many errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"Too many consecutive errors ({consecutive_errors}) for client {client.client_id}, disconnecting")
                    break
                    
                # Continue loop, don't disconnect client yet
    
    async def _process_packet(self, data: str) -> Optional[str]:
        """Process a packet from a client.
        
        Args:
            data: Packet data as string
            
        Returns:
            Response data as string or None
        """
        try:
            # Parse JSON
            packet = json.loads(data)
            
            # Check for acknowledgment packet
            if "_ack" in packet:
                # This is an acknowledgment packet, no response needed
                logger.debug(f"Received acknowledgment for packet {packet['_ack']}")
                return None
                
            # Check for metadata
            meta = packet.pop("_meta", None)
            
            # Process the packet
            response = packet.copy()  # Echo packet for now
            
            # Add acknowledgment if requested
            if meta and meta.get("requires_ack") and meta.get("id"):
                # Send acknowledgment
                ack_response = {"_ack": meta["id"]}
                return json.dumps(ack_response)
                
            # Add metadata to response if needed
            if meta:
                response_meta = {
                    "id": f"resp:{meta.get('id', str(time.time()))}",
                    "timestamp": time.time(),
                    "requires_ack": False
                }
                response["_meta"] = response_meta
                
            return json.dumps(response)
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON packet: {data}")
            self._packet_errors += 1
            return json.dumps({
                "error": "Invalid JSON",
                "_meta": {
                    "id": f"error:{int(time.time())}",
                    "timestamp": time.time(),
                    "requires_ack": False
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing packet: {e}")
            self._packet_errors += 1
            return json.dumps({
                "error": str(e),
                "_meta": {
                    "id": f"error:{int(time.time())}",
                    "timestamp": time.time(),
                    "requires_ack": False
                }
            })
    
    async def stop(self) -> None:
        """Stop the TCP server."""
        if not self.is_running:
            return
        
        logger.info("Stopping TCP server...")
        self._shutdown_event.set()
        
        # Close all client connections
        for client_id, client in list(self._clients.items()):
            try:
                client.writer.close()
                await client.writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing client connection {client_id}: {e}")
                
        # Cancel all client tasks
        for task in self._client_tasks.values():
            task.cancel()
            
        # Clear client data
        self._clients.clear()
        self._client_tasks.clear()
        
        # Stop the server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        
        self._running = False
        self.metrics.record('server_stop_time', self.metrics.measure_time())
        logger.info("TCP server stopped")
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current server metrics."""
        metrics = self.metrics.metrics.copy()
        metrics.update({
            'active_clients': len(self._clients),
            'uptime': self.metrics.measure_time()
        })
        return metrics 