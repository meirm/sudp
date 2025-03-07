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
from typing import Optional, Dict, Set

from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

logger = setup_logging(enable_file_logging=False)

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
        self._clients: Set[asyncio.StreamWriter] = set()
        
        # Performance metrics
        self.metrics = PerformanceMetrics()
    
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
    
    @log_performance("server_start")
    async def start(self) -> None:
        """Start the TCP server."""
        if self.is_running:
            raise RuntimeError("Server is already running")
        
        try:
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
        
        self._clients.add(writer)
        self.metrics.record('active_clients', len(self._clients))
        
        try:
            while not self._shutdown_event.is_set():
                # Read line-delimited JSON
                line = await reader.readline()
                if not line:  # EOF
                    break
                
                # Parse and echo the packet
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
                
                # Echo back
                response = {
                    'payload': packet.payload.hex(),
                    'source_addr': self.host,
                    'source_port': self.port,
                    'dest_addr': packet.source_addr,
                    'dest_port': packet.source_port
                }
                
                writer.write(json.dumps(response).encode() + b'\n')
                await writer.drain()
                
                # Update metrics
                self.metrics.record('packets_sent', 1)
                self.metrics.record('bytes_sent', len(packet.payload))
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_error(logger, e, {'peer': peer})
        finally:
            # Clean up
            self._clients.remove(writer)
            self.metrics.record('active_clients', len(self._clients))
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {peer}")
    
    async def stop(self) -> None:
        """Stop the TCP server."""
        if not self.is_running:
            return
        
        logger.info("Stopping TCP server...")
        self._shutdown_event.set()
        
        # Close all client connections
        for writer in self._clients:
            writer.close()
        await asyncio.gather(*(
            writer.wait_closed() for writer in self._clients
        ))
        self._clients.clear()
        
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