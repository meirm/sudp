"""Tests for UDP packet handling."""

import json
import time
from unittest import TestCase

import pytest

from ..common.packet import UDPPacket


class TestUDPPacket(TestCase):
    """Test cases for UDPPacket class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_payload = b"Hello, World!"
        self.source = ("192.168.1.1", 12345)
        self.destination = ("10.0.0.1", 54321)
        self.packet = UDPPacket.create(
            payload=self.test_payload,
            source=self.source,
            destination=self.destination
        )

    def test_create_packet_with_bytes(self):
        """Test creating a packet with bytes payload."""
        packet = UDPPacket.create(
            payload=b"Test Data",
            source=self.source,
            destination=self.destination
        )
        assert isinstance(packet, UDPPacket)
        assert packet.payload == b"Test Data"
        assert packet.source_addr == self.source[0]
        assert packet.source_port == self.source[1]

    def test_create_packet_with_string(self):
        """Test creating a packet with string payload."""
        packet = UDPPacket.create(
            payload="Test String",
            source=self.source,
            destination=self.destination
        )
        assert isinstance(packet, UDPPacket)
        assert packet.payload == b"Test String"

    def test_packet_validation(self):
        """Test packet validation."""
        # Test invalid payload type
        with pytest.raises(ValueError):
            UDPPacket(
                payload=[1, 2, 3],  # type: ignore
                source_addr=self.source[0],
                source_port=self.source[1],
                dest_addr=self.destination[0],
                dest_port=self.destination[1]
            )

        # Test invalid port numbers
        with pytest.raises(ValueError):
            UDPPacket.create(
                payload=self.test_payload,
                source=(self.source[0], 70000),  # Invalid port
                destination=self.destination
            )

        # Test invalid IP address
        with pytest.raises(ValueError):
            UDPPacket.create(
                payload=self.test_payload,
                source=("invalid.ip", self.source[1]),
                destination=self.destination
            )

    def test_packet_serialization(self):
        """Test packet serialization methods."""
        # Test to_dict
        packet_dict = self.packet.to_dict()
        assert isinstance(packet_dict, dict)
        assert packet_dict["payload"] == self.test_payload.hex()
        assert packet_dict["source_addr"] == self.source[0]
        assert packet_dict["source_port"] == self.source[1]

        # Test to_json
        packet_json = self.packet.to_json()
        assert isinstance(packet_json, str)
        parsed_json = json.loads(packet_json)
        assert parsed_json["payload"] == self.test_payload.hex()

        # Test to_bytes
        packet_bytes = self.packet.to_bytes()
        assert isinstance(packet_bytes, bytes)

    def test_packet_deserialization(self):
        """Test packet deserialization methods."""
        # Test from_dict
        packet_dict = self.packet.to_dict()
        reconstructed = UDPPacket.from_dict(packet_dict)
        assert reconstructed.payload == self.packet.payload
        assert reconstructed.source_addr == self.packet.source_addr
        assert reconstructed.source_port == self.packet.source_port

        # Test from_json
        packet_json = self.packet.to_json()
        reconstructed = UDPPacket.from_json(packet_json)
        assert reconstructed.payload == self.packet.payload

        # Test from_bytes
        packet_bytes = self.packet.to_bytes()
        reconstructed = UDPPacket.from_bytes(packet_bytes)
        assert reconstructed.payload == self.packet.payload

    def test_invalid_deserialization(self):
        """Test deserialization with invalid data."""
        # Test invalid JSON
        with pytest.raises(ValueError):
            UDPPacket.from_json("invalid json")

        # Test invalid bytes
        with pytest.raises(ValueError):
            UDPPacket.from_bytes(b"\xFF\xFF\xFF")  # Invalid UTF-8

        # Test invalid dictionary
        with pytest.raises(ValueError):
            UDPPacket.from_dict({"invalid": "data"})

    def test_packet_metadata(self):
        """Test packet metadata handling."""
        # Test timestamp
        assert isinstance(self.packet.timestamp, float)
        assert self.packet.timestamp <= time.time()

        # Test size calculation
        assert self.packet.size == len(self.test_payload)

        # Test custom timestamp
        custom_time = time.time() - 3600  # 1 hour ago
        packet = UDPPacket(
            payload=self.test_payload,
            source_addr=self.source[0],
            source_port=self.source[1],
            dest_addr=self.destination[0],
            dest_port=self.destination[1],
            timestamp=custom_time
        )
        assert packet.timestamp == custom_time 