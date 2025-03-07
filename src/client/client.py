#!/usr/bin/env python3
"""Main client implementation.

This module provides the main SUDP client that:
1. Runs a local UDP server to receive packets
2. Maintains a TCP connection to the remote server
3. Coordinates packet flow between components
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from .local_server import LocalUDPServer
from .tcp_client import TCPClient
from ..common.packet import UDPPacket
from ..common.logging import setup_logging, log_performance, log_error, PerformanceMetrics

logger = setup_logging(enable_file_logging=False)

class SUDPClient:
    """Main SUDP client implementation.
    
    This client:
    - Runs a local UDP server for receiving packets
    - Maintains a TCP connection to the remote server
    - Handles bidirectional packet flow
    - Provides metrics and logging
    """
    
    def __init__(
        self,
        # Local UDP server settings
        udp_host: str = "127.0.0.1",
        udp_port: int = 5005,
        # Remote server settings
        server_host: str = "127.0.0.1",
        server_port: int = 8080,
        # Optional settings
        buffer_size: int = 65507
    ) -> None:
        """Initialize the SUDP client.
        
        Args:
            udp_host: Local UDP server address
            udp_port: Local UDP server port
            server_host: Remote server address
            server_port: Remote server port
            buffer_size: Maximum packet size
        """
        # Create components
        self.udp_server = LocalUDPServer(
            listen_host=udp_host,
            listen_port=udp_port,
            buffer_size=buffer_size,
            packet_handler=self._handle_local_packet
        )
        
        self.tcp_client = TCPClient(
            server_host=server_host,
            server_port=server_port,
            packet_handler=self._handle_remote_packet
        )
        
        self._running = False
        self._shutdown_event = asyncio.Event()
        self.metrics = PerformanceMetrics()
        
        # Store client addresses for response routing
        self._client_addresses = {}
    
    async def __aenter__(self) -> 'SUDPClient':
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
    
    @property
    def is_running(self) -> bool:
        """Check if the client is running."""
        return self._running
    
    @log_performance("client_start")
    async def start(self) -> None:
        """Start the SUDP client."""
        if self.is_running:
            return
            
        try:
            # Start components
            await self.tcp_client.__aenter__()
            await self.udp_server.__aenter__()
            
            self._running = True
            self._shutdown_event.clear()
            
            logger.info("SUDP client started")
            self.metrics.record('client_start_time', self.metrics.measure_time())
            
        except Exception as e:
            log_error(logger, e, {'phase': 'startup'})
            await self.stop()
            raise
    
    async def _handle_local_packet(self, packet: UDPPacket) -> None:
        """Handle a packet from the local UDP server.
        
        Args:
            packet: The received UDP packet
        """
        try:
            # Store client address for response routing
            client_addr = (packet.source_addr, packet.source_port)
            self._client_addresses[client_addr] = client_addr
            
            await self.tcp_client.send_packet(packet)
            self.metrics.record('packets_forwarded', 1)
            self.metrics.record('bytes_forwarded', len(packet.payload))
            
        except Exception as e:
            log_error(logger, e, {
                'source': 'local',
                'packet_size': len(packet.payload)
            })
    
    async def _handle_remote_packet(self, packet: UDPPacket) -> None:
        """Handle a packet from the remote server.
        
        Args:
            packet: The received UDP packet
        """
        try:
            # Find the original client address
            client_addrs = list(self._client_addresses.values())
            if client_addrs:
                # Use the most recent client address
                client_addr = client_addrs[-1]
                packet.dest_addr = client_addr[0]
                packet.dest_port = client_addr[1]
                
                await self.udp_server.send_response(packet)
                self.metrics.record('packets_returned', 1)
                self.metrics.record('bytes_returned', len(packet.payload))
            else:
                logger.warning("No client address found for response routing")
            
        except Exception as e:
            log_error(logger, e, {
                'source': 'remote',
                'packet_size': len(packet.payload)
            })
    
    async def stop(self) -> None:
        """Stop the SUDP client."""
        if not self.is_running:
            return
            
        logger.info("Stopping SUDP client...")
        self._shutdown_event.set()
        
        # Stop components
        await self.tcp_client.__aexit__(None, None, None)
        await self.udp_server.__aexit__(None, None, None)
        
        self._running = False
        self.metrics.record('client_stop_time', self.metrics.measure_time())
        logger.info("SUDP client stopped")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics from all components."""
        metrics = self.metrics.metrics.copy()
        metrics.update({
            'udp_server': self.udp_server.get_metrics(),
            'tcp_client': self.tcp_client.get_metrics(),
            'uptime': self.metrics.measure_time()
        })
        return metrics 