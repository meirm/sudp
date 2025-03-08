#!/usr/bin/env python3
"""
Error Recovery Demo for SUDP

This example demonstrates:
1. Automatic reconnection when the server goes down
2. Reliable packet delivery with acknowledgments
3. Packet loss handling and retransmission
4. Buffer management for unacknowledged packets

Usage:
    # Start the server in one terminal
    sudpd start --instance recovery_demo --port 11230
    
    # Run this demo in another terminal
    python examples/error_recovery_demo.py
    
    # To simulate server failure, stop the server during the demo
    sudpd stop --instance recovery_demo
    
    # Then restart it to see reconnection
    sudpd start --instance recovery_demo --port 11230
"""

import asyncio
import logging
import sys
import time
import random
import json
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
DEMO_SERVER_PORT = 11230
TOTAL_PACKETS = 50
PACKET_INTERVAL = 0.5  # seconds
PACKET_SIZE = 1024  # bytes

async def packet_handler(packet: UDPPacket) -> None:
    """Handle received packets."""
    logger.info(f"Received response: {len(packet.payload)} bytes from {packet.source_addr}:{packet.source_port}")

async def send_packets(client: TCPClient, count: int) -> None:
    """Send a series of packets to the server."""
    for i in range(count):
        # Create a random payload
        payload = bytes([random.randint(0, 255) for _ in range(PACKET_SIZE)])
        
        # Create a UDP packet
        packet = UDPPacket(
            payload=payload,
            source_addr="127.0.0.1",
            source_port=5000 + i,
            dest_addr="127.0.0.1",
            dest_port=DEMO_SERVER_PORT
        )
        
        try:
            # Send the packet
            await client.send_packet(packet)
            logger.info(f"Sent packet {i+1}/{count} ({len(payload)} bytes)")
            
            # Print metrics every 10 packets
            if (i + 1) % 10 == 0:
                metrics = client.get_metrics()
                logger.info(f"Client metrics: {json.dumps(metrics, indent=2)}")
                
            # Wait before sending next packet
            await asyncio.sleep(PACKET_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error sending packet {i+1}: {e}")
            # Continue with next packet

async def main() -> None:
    """Run the error recovery demo."""
    logger.info("Starting SUDP Error Recovery Demo")
    logger.info(f"Connecting to server on port {DEMO_SERVER_PORT}")
    
    # Create TCP client with error recovery features
    client = TCPClient(
        server_host="127.0.0.1",
        server_port=DEMO_SERVER_PORT,
        packet_handler=packet_handler,
        max_retries=10,
        reconnect_backoff=1.0,
        max_backoff=30.0,
        ack_timeout=3.0,
        enable_reliable_delivery=True
    )
    
    try:
        # Connect to the server
        connected = await client.connect()
        if not connected:
            logger.error("Failed to connect to server, exiting")
            return
            
        logger.info("Connected to server, starting packet transmission")
        
        # Send packets
        await send_packets(client, TOTAL_PACKETS)
        
        # Wait for any pending acknowledgments
        logger.info("Waiting for pending acknowledgments...")
        await asyncio.sleep(5)
        
        # Print final metrics
        metrics = client.get_metrics()
        logger.info(f"Final client metrics: {json.dumps(metrics, indent=2)}")
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Error in demo: {e}")
    finally:
        # Close the client
        await client.close()
        logger.info("Demo completed")

if __name__ == "__main__":
    asyncio.run(main()) 