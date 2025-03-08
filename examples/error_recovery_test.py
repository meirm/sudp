#!/usr/bin/env python3
"""
Focused Error Recovery Test for SUDP

This script demonstrates:
1. Connection recovery after server failure
2. Packet retransmission for reliability
3. Buffer management during disconnection

Usage:
    # Start the server in one terminal
    sudpd start --instance recovery_test --port 11231
    
    # Run this test in another terminal
    python examples/error_recovery_test.py
    
    # The script will automatically stop and restart the server
    # to demonstrate recovery features
"""

import asyncio
import logging
import sys
import time
import random
import json
import subprocess
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sudp.client.tcp_client import TCPClient
from sudp.common.packet import UDPPacket
from sudp.common.logging import setup_logging

# Configure logging
logger = setup_logging(
    enable_console_logging=True,
    log_level=logging.INFO
)

# Global variables
DEMO_SERVER_PORT = 11231
PACKET_SIZE = 1024  # bytes

async def packet_handler(packet: UDPPacket) -> None:
    """Handle received packets."""
    logger.info(f"Received response: {len(packet.payload)} bytes from {packet.source_addr}:{packet.source_port}")

async def send_packet(client: TCPClient, packet_id: int) -> None:
    """Send a single packet to the server."""
    # Create a random payload
    payload = bytes([random.randint(0, 255) for _ in range(PACKET_SIZE)])
    
    # Create a UDP packet
    packet = UDPPacket(
        payload=payload,
        source_addr="127.0.0.1",
        source_port=5000 + packet_id,
        dest_addr="127.0.0.1",
        dest_port=DEMO_SERVER_PORT
    )
    
    try:
        # Send the packet
        await client.send_packet(packet)
        logger.info(f"Sent packet {packet_id} ({len(payload)} bytes)")
    except Exception as e:
        logger.error(f"Error sending packet {packet_id}: {e}")

def run_command(cmd: list) -> tuple:
    """Run a command and return exit code, stdout, and stderr."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr

async def main() -> None:
    """Run the focused error recovery test."""
    logger.info("Starting SUDP Focused Error Recovery Test")
    
    # Start the server
    logger.info("Starting server on port 11231...")
    returncode, stdout, stderr = run_command(
        ["sudpd", "start", "--instance", "recovery_test", "--port", "11231"]
    )
    if returncode != 0:
        logger.error(f"Failed to start server: {stderr}")
        return
    
    logger.info("Server started successfully")
    await asyncio.sleep(2)  # Give server time to initialize
    
    # Create TCP client with error recovery features
    client = TCPClient(
        server_host="127.0.0.1",
        server_port=DEMO_SERVER_PORT,
        packet_handler=packet_handler,
        max_retries=10,
        reconnect_backoff=1.0,
        max_backoff=10.0,
        ack_timeout=2.0,
        enable_reliable_delivery=True
    )
    
    try:
        # Connect to the server
        logger.info("Connecting to server...")
        connected = await client.connect()
        if not connected:
            logger.error("Failed to connect to server, exiting")
            return
            
        logger.info("Connected to server")
        
        # Send a few packets
        logger.info("Sending initial packets...")
        for i in range(5):
            await send_packet(client, i)
            await asyncio.sleep(0.5)
        
        # Print metrics
        metrics = client.get_metrics()
        logger.info(f"Metrics before server stop: {json.dumps(metrics, indent=2)}")
        
        # Stop the server
        logger.info("Stopping server to simulate failure...")
        returncode, stdout, stderr = run_command(
            ["sudpd", "stop", "--instance", "recovery_test"]
        )
        if returncode != 0:
            logger.error(f"Failed to stop server: {stderr}")
        else:
            logger.info("Server stopped successfully")
        
        # Try to send packets while server is down
        logger.info("Attempting to send packets while server is down...")
        for i in range(5, 10):
            await send_packet(client, i)
            await asyncio.sleep(0.5)
        
        # Print metrics
        metrics = client.get_metrics()
        logger.info(f"Metrics during disconnection: {json.dumps(metrics, indent=2)}")
        
        # Restart the server
        logger.info("Restarting server...")
        await asyncio.sleep(5)  # Wait before restarting
        returncode, stdout, stderr = run_command(
            ["sudpd", "start", "--instance", "recovery_test", "--port", "11231"]
        )
        if returncode != 0:
            logger.error(f"Failed to restart server: {stderr}")
            return
            
        logger.info("Server restarted successfully")
        await asyncio.sleep(5)  # Give time for reconnection
        
        # Check if reconnected
        if client.is_connected:
            logger.info("Client successfully reconnected to server")
        else:
            logger.warning("Client failed to reconnect automatically")
        
        # Send more packets
        logger.info("Sending packets after reconnection...")
        for i in range(10, 15):
            await send_packet(client, i)
            await asyncio.sleep(0.5)
        
        # Wait for any pending acknowledgments
        logger.info("Waiting for pending acknowledgments...")
        await asyncio.sleep(5)
        
        # Print final metrics
        metrics = client.get_metrics()
        logger.info(f"Final metrics: {json.dumps(metrics, indent=2)}")
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error in test: {e}")
    finally:
        # Close the client
        await client.close()
        
        # Stop the server
        logger.info("Stopping server...")
        run_command(["sudpd", "stop", "--instance", "recovery_test"])
        
        logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main()) 