#!/usr/bin/env python3
"""Performance benchmarks for SUDP server."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sudp.server.tcp_server import TCPServer


class PerformanceBenchmark(unittest.TestCase):
    """Performance benchmarks for SUDP server."""

    def setUp(self):
        """Set up test environment."""
        # Clean up any existing instances
        self._run_command(["sudpd", "stop", "--instance", "benchmark"])
        time.sleep(1)  # Give time for cleanup

    def tearDown(self):
        """Clean up after tests."""
        # Stop any running instances
        self._run_command(["sudpd", "stop", "--instance", "benchmark"])
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

    def _send_tcp_packet(self, port: int, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], float]:
        """Send a TCP packet to the server and return the response and round-trip time."""
        # Create a TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Connect to the server
                s.connect(('127.0.0.1', port))
                
                # Send the data
                start_time = time.time()
                s.sendall((json.dumps(data) + '\n').encode())
                
                # Receive the response
                response = s.recv(4096).decode().strip()
                end_time = time.time()
                
                # Calculate round-trip time
                rtt = end_time - start_time
                
                # Parse the response
                return json.loads(response), rtt
            except Exception as e:
                print(f"Error sending TCP packet: {e}")
                return None, 0.0

    def test_single_client_throughput(self):
        """Benchmark throughput for a single client."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "benchmark", "--port", "11228"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Prepare test data
        test_data = {"message": "Hello, benchmark!", "benchmark": "single_client"}
        
        # Warm-up
        for _ in range(10):
            self._send_tcp_packet(11228, test_data)
        
        # Run benchmark
        num_requests = 100
        rtts = []
        
        for _ in range(num_requests):
            _, rtt = self._send_tcp_packet(11228, test_data)
            rtts.append(rtt)
        
        # Calculate statistics
        avg_rtt = statistics.mean(rtts)
        min_rtt = min(rtts)
        max_rtt = max(rtts)
        p95_rtt = sorted(rtts)[int(num_requests * 0.95)]
        
        # Calculate throughput (requests per second)
        throughput = num_requests / sum(rtts)
        
        # Print results
        print(f"\nSingle Client Throughput Benchmark:")
        print(f"Requests: {num_requests}")
        print(f"Average RTT: {avg_rtt*1000:.2f} ms")
        print(f"Min RTT: {min_rtt*1000:.2f} ms")
        print(f"Max RTT: {max_rtt*1000:.2f} ms")
        print(f"95th Percentile RTT: {p95_rtt*1000:.2f} ms")
        print(f"Throughput: {throughput:.2f} requests/second")
        
        # Ensure reasonable performance
        self.assertLess(avg_rtt, 0.1, "Average RTT too high")
        self.assertGreater(throughput, 10, "Throughput too low")

    def test_multi_client_throughput(self):
        """Benchmark throughput with multiple clients."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "benchmark", "--port", "11228"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Define client function
        def client_task(client_id: int, num_requests: int) -> List[float]:
            rtts = []
            test_data = {
                "message": f"Hello from client {client_id}",
                "client_id": client_id,
                "benchmark": "multi_client"
            }
            
            # Warm-up
            for _ in range(5):
                self._send_tcp_packet(11228, test_data)
            
            # Run benchmark
            for _ in range(num_requests):
                _, rtt = self._send_tcp_packet(11228, test_data)
                rtts.append(rtt)
            
            return rtts
        
        # Run multiple clients in parallel
        num_clients = 10
        requests_per_client = 50
        total_requests = num_clients * requests_per_client
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            results = list(executor.map(
                lambda client_id: client_task(client_id, requests_per_client), 
                range(num_clients)
            ))
        end_time = time.time()
        
        # Flatten results
        all_rtts = [rtt for client_rtts in results for rtt in client_rtts]
        
        # Calculate statistics
        avg_rtt = statistics.mean(all_rtts)
        min_rtt = min(all_rtts)
        max_rtt = max(all_rtts)
        p95_rtt = sorted(all_rtts)[int(len(all_rtts) * 0.95)]
        
        # Calculate throughput (requests per second)
        total_time = end_time - start_time
        throughput = total_requests / total_time
        
        # Print results
        print(f"\nMulti-Client Throughput Benchmark:")
        print(f"Clients: {num_clients}")
        print(f"Requests per client: {requests_per_client}")
        print(f"Total requests: {total_requests}")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average RTT: {avg_rtt*1000:.2f} ms")
        print(f"Min RTT: {min_rtt*1000:.2f} ms")
        print(f"Max RTT: {max_rtt*1000:.2f} ms")
        print(f"95th Percentile RTT: {p95_rtt*1000:.2f} ms")
        print(f"Throughput: {throughput:.2f} requests/second")
        
        # Ensure reasonable performance
        self.assertLess(avg_rtt, 0.5, "Average RTT too high")
        self.assertGreater(throughput, 50, "Throughput too low")

    def test_large_packet_performance(self):
        """Benchmark performance with large packets."""
        # Start a server instance
        returncode, stdout, stderr = self._run_command(
            ["sudpd", "start", "--instance", "benchmark", "--port", "11228"]
        )
        self.assertEqual(returncode, 0, f"Failed to start instance: {stderr}")
        
        # Give it time to start
        time.sleep(2)
        
        # Define packet sizes to test
        packet_sizes = [1000, 10000, 100000]
        
        for size in packet_sizes:
            # Create test data with specified size
            test_data = {
                "message": "X" * size,
                "size": size,
                "benchmark": "large_packet"
            }
            
            # Warm-up
            for _ in range(3):
                self._send_tcp_packet(11228, test_data)
            
            # Run benchmark
            num_requests = 10
            rtts = []
            
            for _ in range(num_requests):
                _, rtt = self._send_tcp_packet(11228, test_data)
                rtts.append(rtt)
            
            # Calculate statistics
            avg_rtt = statistics.mean(rtts)
            min_rtt = min(rtts)
            max_rtt = max(rtts)
            
            # Calculate throughput (bytes per second)
            total_bytes = size * num_requests
            throughput_bytes = total_bytes / sum(rtts)
            throughput_mb = throughput_bytes / (1024 * 1024)
            
            # Print results
            print(f"\nLarge Packet Benchmark (Size: {size} bytes):")
            print(f"Requests: {num_requests}")
            print(f"Average RTT: {avg_rtt*1000:.2f} ms")
            print(f"Min RTT: {min_rtt*1000:.2f} ms")
            print(f"Max RTT: {max_rtt*1000:.2f} ms")
            print(f"Throughput: {throughput_mb:.2f} MB/second")
            
            # Ensure reasonable performance (adjust thresholds based on expected performance)
            self.assertGreater(throughput_mb, 0.1, f"Throughput too low for {size} bytes")


if __name__ == "__main__":
    unittest.main() 