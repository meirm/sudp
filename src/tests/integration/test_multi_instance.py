#!/usr/bin/env python3
"""Integration tests for multi-instance functionality."""

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

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sudp.server.daemon import ServerDaemon
from sudp.common.config import create_server_config
import argparse


class MultiInstanceTest(unittest.TestCase):
    """Test multi-instance functionality."""

    def setUp(self):
        """Set up test environment."""
        # Clean up any existing instances
        self._run_command(["sudpd", "stop", "--instance", "test1"])
        self._run_command(["sudpd", "stop", "--instance", "test2"])
        time.sleep(1)  # Give time for cleanup

    def tearDown(self):
        """Clean up after tests."""
        # Stop any running instances
        self._run_command(["sudpd", "stop", "--instance", "test1"])
        self._run_command(["sudpd", "stop", "--instance", "test2"])
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

    def _start_instance(self, instance_name: str, port: int) -> subprocess.Popen:
        """Start a server instance in the background."""
        process = subprocess.Popen(
            ["sudpd", "start", "--instance", instance_name, "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Give it time to start
        time.sleep(2)
        return process

    def _check_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def _send_udp_packet(self, port: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a UDP packet to the server and return the response."""
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
                print(f"Error sending UDP packet: {e}")
                return None

    def test_start_stop_single_instance(self):
        """Test starting and stopping a single instance."""
        # Start an instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test1", "--port", "11224"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Check if the instance is running
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "status", "--instance", "test1"]
        )
        self.assertEqual(returncode, 0, f"Failed to check status: {stderr}")
        self.assertIn("is running", stdout, "Instance is not running")
        
        # Check if the port is in use
        self.assertTrue(self._check_port_in_use(11224), "Port 11224 is not in use")
        
        # Stop the instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "stop", "--instance", "test1"]
        )
        self.assertEqual(returncode, 0, f"Failed to stop instance: {stderr}")
        
        # Check if the instance is stopped
        time.sleep(1)  # Give it time to stop
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "status", "--instance", "test1"]
        )
        self.assertEqual(returncode, 0, f"Failed to check status: {stderr}")
        self.assertIn("is not running", stdout, "Instance is still running")
        
        # Check if the port is free
        self.assertFalse(self._check_port_in_use(11224), "Port 11224 is still in use")

    def test_multiple_instances(self):
        """Test running multiple instances simultaneously."""
        # Start first instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test1", "--port", "11224"]
        )
        self.assertEqual(returncode, 0, f"Failed to start first instance: {stderr}")
        
        # Start second instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test2", "--port", "11225"]
        )
        self.assertEqual(returncode, 0, f"Failed to start second instance: {stderr}")
        
        # Check if both instances are running
        returncode, stdout, stderr = self._run_command(["sudpd", "list"])
        self.assertEqual(returncode, 0, f"Failed to list instances: {stderr}")
        self.assertIn("test1", stdout, "First instance not found in list")
        self.assertIn("test2", stdout, "Second instance not found in list")
        
        # Check if both ports are in use
        self.assertTrue(self._check_port_in_use(11224), "Port 11224 is not in use")
        self.assertTrue(self._check_port_in_use(11225), "Port 11225 is not in use")
        
        # Stop both instances
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "stop", "--instance", "test1"]
        )
        self.assertEqual(returncode, 0, f"Failed to stop first instance: {stderr}")
        
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "stop", "--instance", "test2"]
        )
        self.assertEqual(returncode, 0, f"Failed to stop second instance: {stderr}")
        
        # Check if both instances are stopped
        time.sleep(1)  # Give them time to stop
        returncode, stdout, stderr = self._run_command(["sudpd", "list"])
        self.assertEqual(returncode, 0, f"Failed to list instances: {stderr}")
        if "test1" in stdout:
            self.assertIn("STOPPED", stdout, "First instance is not stopped")
        if "test2" in stdout:
            self.assertIn("STOPPED", stdout, "Second instance is not stopped")

    def test_instance_communication(self):
        """Test sending packets to different instances."""
        # Start two instances
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test1", "--port", "11224"]
        )
        self.assertEqual(returncode, 0, f"Failed to start first instance: {stderr}")
        
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test2", "--port", "11225"]
        )
        self.assertEqual(returncode, 0, f"Failed to start second instance: {stderr}")
        
        # Send a packet to the first instance
        test_data1 = {"message": "Hello, test1!", "source": "integration_test"}
        response1 = self._send_udp_packet(11224, test_data1)
        self.assertIsNotNone(response1, "No response from first instance")
        self.assertEqual(response1["message"], test_data1["message"], 
                         "Response from first instance doesn't match")
        
        # Send a packet to the second instance
        test_data2 = {"message": "Hello, test2!", "source": "integration_test"}
        response2 = self._send_udp_packet(11225, test_data2)
        self.assertIsNotNone(response2, "No response from second instance")
        self.assertEqual(response2["message"], test_data2["message"], 
                         "Response from second instance doesn't match")

    def test_auto_port_allocation(self):
        """Test automatic port allocation."""
        # Start an instance with automatic port allocation
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "test1", "--port", "0"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Check if the instance is running
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "status", "--instance", "test1"]
        )
        self.assertEqual(returncode, 0, f"Failed to check status: {stderr}")
        self.assertIn("is running", stdout, "Instance is not running")
        
        # Extract the port from the status output
        import re
        port_match = re.search(r"port: (\d+)", stdout)
        self.assertIsNotNone(port_match, "Could not find port in status output")
        port = int(port_match.group(1))
        self.assertGreater(port, 0, "Invalid port number")
        
        # Check if the port is in use
        self.assertTrue(self._check_port_in_use(port), f"Port {port} is not in use")
        
        # Stop the instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "stop", "--instance", "test1"]
        )
        self.assertEqual(returncode, 0, f"Failed to stop instance: {stderr}")


if __name__ == "__main__":
    unittest.main() 