"""UDP Socket Management Module.

This module provides the core functionality for managing UDP sockets in the SUDP system.
It includes non-blocking operations, buffer management, and error handling.
"""

import asyncio
import logging
import socket
from typing import Optional, Tuple, Union

from .packet import UDPPacket

logger = logging.getLogger(__name__)

class UDPSocket:
    """A non-blocking UDP socket wrapper with buffer management.

    This class provides a high-level interface for UDP socket operations,
    including non-blocking I/O and automatic buffer management.

    Attributes:
        address (str): The IP address to bind to
        port (int): The port number to bind to
        buffer_size (int): Maximum size of the receive buffer
        socket (socket.socket): The underlying UDP socket
    """

    def __init__(self, address: str, port: int, buffer_size: int = 65507):
        """Initialize the UDP socket.

        Args:
            address (str): IP address to bind to
            port (int): Port number to bind to
            buffer_size (int, optional): Maximum buffer size. Defaults to 65507 (max UDP packet size).

        Raises:
            ValueError: If the address or port is invalid
            OSError: If the socket cannot be created or bound
        """
        self.address = address
        self.port = port
        self.buffer_size = buffer_size
        self._socket: Optional[socket.socket] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    @property
    def is_running(self) -> bool:
        """Check if the socket is running.

        Returns:
            bool: True if the socket is created and bound, False otherwise
        """
        return self._socket is not None

    async def start(self):
        """Start the UDP socket.

        Creates and binds the socket in non-blocking mode.

        Raises:
            OSError: If the socket cannot be created or bound
            RuntimeError: If the socket is already running
        """
        if self.is_running:
            raise RuntimeError("Socket is already running")

        try:
            # Create a UDP socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setblocking(False)

            # Bind the socket
            self._socket.bind((self.address, self.port))
            self._loop = asyncio.get_running_loop()

            logger.info(f"UDP socket bound to {self.address}:{self.port}")
        except OSError as e:
            if self._socket:
                self._socket.close()
                self._socket = None
            logger.error(f"Failed to start UDP socket: {e}")
            raise

    async def stop(self):
        """Stop the UDP socket.

        Closes the socket and releases resources.
        """
        if self._socket:
            self._socket.close()
            self._socket = None
            self._loop = None
            logger.info("UDP socket closed")

    async def receive(self) -> Tuple[bytes, Tuple[str, int]]:
        """Receive data from the socket.

        Returns:
            Tuple[bytes, Tuple[str, int]]: Tuple containing the received data and the sender's address

        Raises:
            RuntimeError: If the socket is not running
            OSError: If there's an error receiving data
        """
        if not self.is_running or not self._loop:
            raise RuntimeError("Socket is not running")

        try:
            data, addr = await self._loop.sock_recvfrom(self._socket, self.buffer_size)
            logger.debug(f"Received {len(data)} bytes from {addr}")
            return data, addr
        except OSError as e:
            logger.error(f"Error receiving data: {e}")
            raise

    async def send(self, data: Union[bytes, UDPPacket], addr: Optional[Tuple[str, int]] = None) -> int:
        """Send data through the socket.

        Args:
            data (Union[bytes, UDPPacket]): Data to send (either raw bytes or a UDPPacket)
            addr (Optional[Tuple[str, int]], optional): Destination address. 
                Required for bytes, ignored for UDPPacket. Defaults to None.

        Returns:
            int: Number of bytes sent

        Raises:
            RuntimeError: If the socket is not running
            ValueError: If addr is not provided for bytes data
            OSError: If there's an error sending data
        """
        if not self.is_running or not self._loop:
            raise RuntimeError("Socket is not running")

        try:
            if isinstance(data, UDPPacket):
                send_data = data.payload
                dest_addr = (data.dest_addr, data.dest_port)
            else:
                if not addr:
                    raise ValueError("Address required for raw bytes")
                send_data = data
                dest_addr = addr

            bytes_sent = await self._loop.sock_sendto(self._socket, send_data, dest_addr)
            logger.debug(f"Sent {bytes_sent} bytes to {dest_addr}")
            return bytes_sent

        except OSError as e:
            logger.error(f"Error sending data: {e}")
            raise

    async def receive_packet(self) -> UDPPacket:
        """Receive data and create a UDPPacket.

        Returns:
            UDPPacket: A new packet containing the received data

        Raises:
            RuntimeError: If the socket is not running
            OSError: If there's an error receiving data
        """
        data, (src_addr, src_port) = await self.receive()
        return UDPPacket(
            payload=data,
            source_addr=src_addr,
            source_port=src_port,
            dest_addr=self.address,
            dest_port=self.port
        ) 