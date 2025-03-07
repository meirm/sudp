"""Tests for UDP socket management."""

import asyncio
import subprocess
import sys
import time
from unittest import IsolatedAsyncioTestCase

import pytest

from ..common.packet import UDPPacket
from ..common.socket import UDPSocket


class TestUDPSocket(IsolatedAsyncioTestCase):
    """Test cases for UDPSocket class."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.test_port = 5000
        self.socket = UDPSocket("127.0.0.1", self.test_port)
        await self.socket.start()

    async def asyncTearDown(self):
        """Clean up test fixtures."""
        await self.socket.stop()

    async def test_socket_lifecycle(self):
        """Test socket creation, start, and stop."""
        # Test initial state
        assert self.socket.is_running

        # Test stopping
        await self.socket.stop()
        assert not self.socket.is_running

        # Test restarting
        await self.socket.start()
        assert self.socket.is_running

    async def test_socket_context_manager(self):
        """Test socket context manager."""
        await self.socket.stop()  # Clean up the setUp socket
        
        async with UDPSocket("127.0.0.1", self.test_port) as sock:
            assert sock.is_running
            assert sock.port == self.test_port
        
        assert not sock.is_running

    async def test_invalid_socket_operations(self):
        """Test error handling for invalid operations."""
        # Test starting an already running socket
        with pytest.raises(RuntimeError):
            await self.socket.start()

        # Test operations on stopped socket
        await self.socket.stop()
        with pytest.raises(RuntimeError):
            await self.socket.receive()
        with pytest.raises(RuntimeError):
            await self.socket.send(b"test", ("127.0.0.1", 5001))

    async def test_send_receive_bytes(self):
        """Test sending and receiving raw bytes."""
        test_data = b"Hello, World!"
        test_port = self.test_port + 1

        # Create a second socket for receiving
        async with UDPSocket("127.0.0.1", test_port) as receiver:
            # Send data
            bytes_sent = await self.socket.send(
                test_data, 
                ("127.0.0.1", test_port)
            )
            assert bytes_sent == len(test_data)

            # Receive data
            data, addr = await receiver.receive()
            assert data == test_data
            assert addr == ("127.0.0.1", self.test_port)

    async def test_send_receive_packet(self):
        """Test sending and receiving UDPPacket."""
        test_port = self.test_port + 2
        
        # Create test packet
        packet = UDPPacket(
            payload=b"Test packet",
            source_addr="127.0.0.1",
            source_port=self.test_port,
            dest_addr="127.0.0.1",
            dest_port=test_port
        )

        # Create a second socket for receiving
        async with UDPSocket("127.0.0.1", test_port) as receiver:
            # Send packet
            bytes_sent = await self.socket.send(packet)
            assert bytes_sent == len(packet.payload)

            # Receive packet
            received_packet = await receiver.receive_packet()
            assert received_packet.payload == packet.payload
            assert received_packet.source_addr == "127.0.0.1"
            assert received_packet.source_port == self.test_port

    @pytest.mark.integration
    async def test_netcat_integration(self):
        """Test UDP socket with netcat.
        
        This test requires netcat (nc) to be installed on the system.
        """
        if sys.platform == "win32":
            pytest.skip("Netcat tests not supported on Windows")

        test_message = "Hello from netcat!"
        test_port = self.test_port + 3

        # Start netcat in a separate process
        nc_process = subprocess.Popen(
            ["nc", "-u", "127.0.0.1", str(test_port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        try:
            # Create socket for the test
            async with UDPSocket("127.0.0.1", test_port) as sock:
                # Send test message through netcat
                nc_process.stdin.write(f"{test_message}\n".encode())
                nc_process.stdin.flush()

                # Receive data through our socket
                data, addr = await sock.receive()
                received_message = data.decode().strip()
                assert received_message == test_message

                # Send response back through our socket
                response = b"Response from socket"
                await sock.send(response, addr)

                # Give netcat time to receive the response
                await asyncio.sleep(0.1)

        finally:
            # Clean up netcat process
            nc_process.terminate()
            nc_process.wait(timeout=1) 