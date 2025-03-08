#!/usr/bin/env python3
"""Integration tests for TCP server functionality."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sudp.server.tcp_server import TCPServer


class TCPServerTest(unittest.TestCase):
    """Test TCP server functionality."""

    def setUp(self):
        """Set up test environment."""
        # Clean up any existing instances
        self._run_command(["sudpd", "stop", "--instance", "test_tcp"])
        time.sleep(1)  # Give time for cleanup

    def tearDown(self):
        """Clean up after tests."""
        # Stop any running instances
        self._run_command(["sudpd", "stop", "--instance", "test_tcp"])
        time.sleep(1)  # Give time for cleanup

    def _run_command(self, cmd: List[str]) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, and stderr."""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def _send_tcp_packet(self, port: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a TCP packet to the server and return the response."""
        # Create a TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Connect to the server
                s.connect(('127.0.0.1', port))
                
                # Send the data
                s.sendall((json.dumps(data) + '\n').encode())
                
                # Receive the response
                response = s.recv(4096).decode().strip()
                
                # Parse the response
                return json.loads(response)
            except Exception as e:
                print(f"Error sending TCP packet: {e}")
                return None

    def test_server_echo(self):
        """Test that the server echoes back packets."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test_tcp", "--port", "11226"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Send a packet
        test_data = {"message": "Hello, server!", "source": "integration_test"}
        response = self._send_tcp_packet(11226, test_data)
        
        # Check the response
        self.assertIsNotNone(response, "No response from server")
        self.assertEqual(response["message"], test_data["message"], 
                         "Response message doesn't match")
        self.assertEqual(response["source"], test_data["source"], 
                         "Response source doesn't match")

    def test_multiple_clients(self):
        """Test that the server can handle multiple clients."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test_tcp", "--port", "11226"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Define client function
        def client_task(client_id: int) -> bool:
            test_data = {
                "message": f"Hello from client {client_id}",
                "client_id": client_id
            }
            response = self._send_tcp_packet(11226, test_data)
            if response is None:
                return False
            return (response["message"] == test_data["message"] and 
                    response["client_id"] == test_data["client_id"])
        
        # Run multiple clients in parallel
        num_clients = 5
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            results = list(executor.map(client_task, range(num_clients)))
        
        # Check that all clients received correct responses
        self.assertEqual(len(results), num_clients, "Not all clients completed")
        self.assertTrue(all(results), "Not all clients received correct responses")

    def test_invalid_json(self):
        """Test that the server handles invalid JSON gracefully."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test_tcp", "--port", "11226"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Send invalid JSON
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Connect to the server
                s.connect(('127.0.0.1', 11226))
                
                # Send invalid JSON
                s.sendall(b'{"invalid": "json"\n')
                
                # Receive the response
                response = s.recv(4096).decode().strip()
                
                # Parse the response
                response_data = json.loads(response)
                
                # Check that it contains an error message
                self.assertIn("error", response_data, "No error message in response")
            except Exception as e:
                self.fail(f"Error testing invalid JSON: {e}")

    def test_large_packet(self):
        """Test that the server can handle large packets."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test_tcp", "--port", "11226"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Create a large packet (100KB)
        large_data = "X" * 100000
        test_data = {"message": large_data, "type": "large_packet"}
        
        # Send the packet
        response = self._send_tcp_packet(11226, test_data)
        
        # Check the response
        self.assertIsNotNone(response, "No response from server")
        self.assertEqual(len(response["message"]), len(large_data), 
                         "Response message size doesn't match")
        self.assertEqual(response["type"], test_data["type"], 
                         "Response type doesn't match")

    async def _async_server_test(self):
        """Run an async server test."""
        # Create a server directly
        server = TCPServer(host="127.0.0.1", port=11227, max_clients=10)
        
        # Start the server
        async with server:
            # Send a packet
            test_data = {"message": "Hello, async server!", "source": "async_test"}
            client_task = asyncio.create_task(self._async_client(11227, test_data))
            
            # Wait for the client to complete
            response = await client_task
            
            # Check the response
            self.assertIsNotNone(response, "No response from async server")
            self.assertEqual(response["message"], test_data["message"], 
                            "Response message doesn't match")
            self.assertEqual(response["source"], test_data["source"], 
                            "Response source doesn't match")

    async def _async_client(self, port: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a packet to the server asynchronously."""
        try:
            # Connect to the server
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            
            # Send the data
            writer.write((json.dumps(data) + '\n').encode())
            await writer.drain()
            
            # Receive the response
            response = await reader.readline()
            
            # Close the connection
            writer.close()
            await writer.wait_closed()
            
            # Parse the response
            return json.loads(response.decode().strip())
        except Exception as e:
            print(f"Error in async client: {e}")
            return None

    def test_async_server(self):
        """Test the server using asyncio directly."""
        asyncio.run(self._async_server_test())


if __name__ == "__main__":
    unittest.main() 