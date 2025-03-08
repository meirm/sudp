#!/usr/bin/env python3
"""Error recovery utilities for SUDP.

This module provides:
- Connection recovery mechanisms
- Packet loss detection and handling
- Buffer management for reliable delivery
- Automatic reconnection with exponential backoff
"""

import asyncio
import logging
import time
import random
from typing import Optional, Callable, Dict, Any, List, Tuple, Set, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PacketBuffer:
    """Buffer for tracking sent packets that need acknowledgment."""
    max_size: int = 1000
    timeout_seconds: float = 5.0
    packets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    packet_ids: Set[str] = field(default_factory=set)
    
    def add(self, packet_id: str, packet_data: Dict[str, Any]) -> None:
        """Add a packet to the buffer.
        
        Args:
            packet_id: Unique ID for the packet
            packet_data: Packet data to store
        """
        # If buffer is full, remove oldest packet
        if len(self.packets) >= self.max_size:
            oldest_id = next(iter(self.packet_ids))
            self.packet_ids.remove(oldest_id)
            self.packets.pop(oldest_id, None)
            
        # Add new packet
        self.packets[packet_id] = {
            "data": packet_data,
            "timestamp": time.time(),
            "retries": 0
        }
        self.packet_ids.add(packet_id)
    
    def acknowledge(self, packet_id: str) -> None:
        """Acknowledge receipt of a packet.
        
        Args:
            packet_id: ID of the packet to acknowledge
        """
        if packet_id in self.packets:
            self.packets.pop(packet_id, None)
            self.packet_ids.remove(packet_id)
    
    def get_unacknowledged(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get packets that haven't been acknowledged and have timed out.
        
        Returns:
            List of (packet_id, packet_data) tuples
        """
        now = time.time()
        result = []
        
        for packet_id, packet_info in list(self.packets.items()):
            if now - packet_info["timestamp"] > self.timeout_seconds:
                # Update timestamp and increment retry count
                packet_info["timestamp"] = now
                packet_info["retries"] += 1
                result.append((packet_id, packet_info["data"]))
                
        return result
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.packets.clear()
        self.packet_ids.clear()


class ConnectionManager:
    """Manages connection state and recovery.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Connection state tracking
    - Retry management
    """
    
    def __init__(
        self,
        connect_func: Callable[[], Awaitable[None]],
        max_retries: int = 10,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        jitter: float = 0.1
    ) -> None:
        """Initialize the connection manager.
        
        Args:
            connect_func: Async function to establish connection
            max_retries: Maximum number of connection retries
            initial_backoff: Initial backoff time in seconds
            max_backoff: Maximum backoff time in seconds
            jitter: Random jitter factor (0-1) to add to backoff
        """
        self.connect_func = connect_func
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.jitter = jitter
        
        self._connected = False
        self._connecting = False
        self._retry_count = 0
        self._last_error: Optional[Exception] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    @property
    def is_connecting(self) -> bool:
        """Check if currently attempting to connect."""
        return self._connecting
    
    @property
    def last_error(self) -> Optional[Exception]:
        """Get the last connection error."""
        return self._last_error
    
    @property
    def retry_count(self) -> int:
        """Get the current retry count."""
        return self._retry_count
    
    def _calculate_backoff(self) -> float:
        """Calculate backoff time with exponential increase and jitter.
        
        Returns:
            Backoff time in seconds
        """
        backoff = min(
            self.initial_backoff * (2 ** self._retry_count),
            self.max_backoff
        )
        
        # Add jitter
        jitter_amount = backoff * self.jitter
        backoff += random.uniform(-jitter_amount, jitter_amount)
        
        return max(backoff, 0.1)  # Ensure minimum backoff
    
    async def connect(self) -> bool:
        """Establish connection with retry logic.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._connected:
            return True
            
        if self._connecting:
            # Wait for existing connection attempt
            while self._connecting:
                await asyncio.sleep(0.1)
            return self._connected
            
        self._connecting = True
        self._retry_count = 0
        
        try:
            # Try to connect
            await self.connect_func()
            self._connected = True
            self._last_error = None
            logger.info("Connection established successfully")
            return True
            
        except Exception as e:
            self._last_error = e
            self._connected = False
            logger.error(f"Connection failed: {e}")
            
            # Start reconnection task
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
                
            return False
            
        finally:
            self._connecting = False
    
    async def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        while not self._connected and self._retry_count < self.max_retries:
            self._retry_count += 1
            backoff = self._calculate_backoff()
            
            logger.info(f"Reconnection attempt {self._retry_count}/{self.max_retries} in {backoff:.2f}s")
            await asyncio.sleep(backoff)
            
            if self._connected:
                break
                
            self._connecting = True
            try:
                await self.connect_func()
                self._connected = True
                self._last_error = None
                logger.info(f"Reconnected successfully after {self._retry_count} attempts")
                
            except Exception as e:
                self._last_error = e
                logger.error(f"Reconnection attempt {self._retry_count} failed: {e}")
                
            finally:
                self._connecting = False
                
        if not self._connected:
            logger.error(f"Failed to reconnect after {self.max_retries} attempts")
    
    def connection_lost(self) -> None:
        """Handle connection loss and trigger reconnection."""
        if not self._connected:
            return
            
        self._connected = False
        logger.warning("Connection lost, scheduling reconnection")
        
        # Start reconnection task if not already running
        if not self._reconnect_task or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    def reset(self) -> None:
        """Reset connection state."""
        self._connected = False
        self._connecting = False
        self._retry_count = 0
        self._last_error = None
        
        # Cancel reconnection task if running
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None


class ReliableChannel:
    """Reliable communication channel with packet acknowledgment.
    
    Features:
    - Packet sequence numbering
    - Acknowledgment tracking
    - Automatic retransmission
    - Flow control
    """
    
    def __init__(
        self,
        send_func: Callable[[Dict[str, Any]], Awaitable[None]],
        max_buffer_size: int = 1000,
        ack_timeout: float = 5.0,
        max_retries: int = 5
    ) -> None:
        """Initialize the reliable channel.
        
        Args:
            send_func: Async function to send a packet
            max_buffer_size: Maximum buffer size for unacknowledged packets
            ack_timeout: Timeout for acknowledgments in seconds
            max_retries: Maximum number of retransmission attempts
        """
        self.send_func = send_func
        self.max_retries = max_retries
        
        self.buffer = PacketBuffer(
            max_size=max_buffer_size,
            timeout_seconds=ack_timeout
        )
        
        self._next_seq_num = 0
        self._retransmit_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
    
    def _get_next_seq_num(self) -> int:
        """Get the next sequence number.
        
        Returns:
            Next sequence number
        """
        seq_num = self._next_seq_num
        self._next_seq_num = (self._next_seq_num + 1) % (2**32)  # 32-bit sequence number
        return seq_num
    
    async def start(self) -> None:
        """Start the reliable channel."""
        self._shutdown_event.clear()
        
        # Start retransmission task
        if not self._retransmit_task or self._retransmit_task.done():
            self._retransmit_task = asyncio.create_task(self._retransmit_loop())
    
    async def stop(self) -> None:
        """Stop the reliable channel."""
        self._shutdown_event.set()
        
        # Wait for retransmission task to complete
        if self._retransmit_task and not self._retransmit_task.done():
            self._retransmit_task.cancel()
            try:
                await self._retransmit_task
            except asyncio.CancelledError:
                pass
                
        # Clear buffer
        self.buffer.clear()
    
    async def send(self, data: Dict[str, Any]) -> str:
        """Send data with reliability guarantees.
        
        Args:
            data: Data to send
            
        Returns:
            Packet ID
        """
        # Add sequence number and create packet ID
        seq_num = self._get_next_seq_num()
        packet_id = f"{int(time.time())}:{seq_num}"
        
        # Add metadata for reliable delivery
        packet_data = data.copy()
        packet_data["_meta"] = {
            "id": packet_id,
            "seq": seq_num,
            "timestamp": time.time(),
            "requires_ack": True
        }
        
        # Add to buffer before sending
        self.buffer.add(packet_id, packet_data)
        
        # Send the packet
        try:
            await self.send_func(packet_data)
            logger.debug(f"Sent packet {packet_id}")
        except Exception as e:
            logger.error(f"Error sending packet {packet_id}: {e}")
            # Keep in buffer for retransmission
            
        return packet_id
    
    def acknowledge(self, packet_id: str) -> None:
        """Acknowledge receipt of a packet.
        
        Args:
            packet_id: ID of the packet to acknowledge
        """
        self.buffer.acknowledge(packet_id)
        logger.debug(f"Acknowledged packet {packet_id}")
    
    async def _retransmit_loop(self) -> None:
        """Loop to retransmit unacknowledged packets."""
        while not self._shutdown_event.is_set():
            try:
                # Get packets that need retransmission
                for packet_id, packet_data in self.buffer.get_unacknowledged():
                    # Check if max retries reached
                    if packet_data.get("_meta", {}).get("retries", 0) >= self.max_retries:
                        logger.warning(f"Max retries reached for packet {packet_id}, giving up")
                        self.buffer.acknowledge(packet_id)  # Remove from buffer
                        continue
                        
                    # Retransmit
                    try:
                        logger.debug(f"Retransmitting packet {packet_id}")
                        await self.send_func(packet_data)
                    except Exception as e:
                        logger.error(f"Error retransmitting packet {packet_id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error in retransmission loop: {e}")
                
            # Wait before next check
            await asyncio.sleep(1.0) 