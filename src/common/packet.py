"""UDP Packet handling module.

This module provides the core functionality for handling UDP packets in the SUDP system.
It includes packet serialization, deserialization, validation, and metadata management.
"""

import dataclasses
import json
import socket
import time
from typing import Optional, Tuple, Union


@dataclasses.dataclass
class UDPPacket:
    """Represents a UDP packet with metadata and payload.

    Attributes:
        payload (bytes): The actual data being transmitted
        source_addr (str): Source IP address
        source_port (int): Source port number
        dest_addr (Optional[str]): Destination IP address
        dest_port (Optional[int]): Destination port number
        timestamp (float): Unix timestamp when the packet was created
        size (int): Size of the payload in bytes
    """

    payload: bytes
    source_addr: str
    source_port: int
    dest_addr: Optional[str] = None
    dest_port: Optional[int] = None
    timestamp: float = dataclasses.field(default_factory=time.time)
    size: int = dataclasses.field(init=False)

    def __post_init__(self):
        """Initialize calculated fields after instance creation."""
        self.size = len(self.payload)
        self._validate()

    def _validate(self) -> None:
        """Validate packet attributes.

        Raises:
            ValueError: If any of the packet attributes are invalid
        """
        if not isinstance(self.payload, bytes):
            raise ValueError("Payload must be bytes")
        
        if not 0 <= self.source_port <= 65535:
            raise ValueError("Source port must be between 0 and 65535")
            
        if self.dest_port is not None and not 0 <= self.dest_port <= 65535:
            raise ValueError("Destination port must be between 0 and 65535")

        try:
            socket.inet_aton(self.source_addr)
            if self.dest_addr is not None:
                socket.inet_aton(self.dest_addr)
        except socket.error:
            raise ValueError("Invalid IP address format")

    def to_dict(self) -> dict:
        """Convert packet to dictionary representation.

        Returns:
            dict: Dictionary containing packet data and metadata
        """
        return {
            "payload": self.payload.hex(),  # Convert bytes to hex string for JSON
            "source_addr": self.source_addr,
            "source_port": self.source_port,
            "dest_addr": self.dest_addr,
            "dest_port": self.dest_port,
            "timestamp": self.timestamp,
            "size": self.size
        }

    def to_json(self) -> str:
        """Convert packet to JSON string.

        Returns:
            str: JSON representation of the packet
        """
        return json.dumps(self.to_dict())

    def to_bytes(self) -> bytes:
        """Serialize packet to bytes for transmission.

        Returns:
            bytes: Serialized packet data
        """
        # Convert to JSON and then to bytes
        return self.to_json().encode('utf-8')

    @classmethod
    def from_dict(cls, data: dict) -> 'UDPPacket':
        """Create a packet from dictionary data.

        Args:
            data (dict): Dictionary containing packet data

        Returns:
            UDPPacket: New packet instance

        Raises:
            ValueError: If the dictionary contains invalid data
        """
        try:
            # Convert hex string back to bytes
            payload = bytes.fromhex(data["payload"])
            return cls(
                payload=payload,
                source_addr=data["source_addr"],
                source_port=data["source_port"],
                dest_addr=data.get("dest_addr"),
                dest_port=data.get("dest_port"),
                timestamp=data.get("timestamp", time.time())
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid packet data: {str(e)}")

    @classmethod
    def from_json(cls, json_str: str) -> 'UDPPacket':
        """Create a packet from JSON string.

        Args:
            json_str (str): JSON string containing packet data

        Returns:
            UDPPacket: New packet instance

        Raises:
            ValueError: If the JSON string is invalid or contains invalid data
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {str(e)}")

    @classmethod
    def from_bytes(cls, data: bytes) -> 'UDPPacket':
        """Create a packet from bytes.

        Args:
            data (bytes): Serialized packet data

        Returns:
            UDPPacket: New packet instance

        Raises:
            ValueError: If the byte data is invalid or contains invalid packet data
        """
        try:
            json_str = data.decode('utf-8')
            return cls.from_json(json_str)
        except UnicodeDecodeError as e:
            raise ValueError(f"Invalid byte data: {str(e)}")

    @classmethod
    def create(cls, 
               payload: Union[bytes, str], 
               source: Tuple[str, int], 
               destination: Optional[Tuple[str, int]] = None) -> 'UDPPacket':
        """Create a new UDP packet with the given payload and addressing information.

        Args:
            payload (Union[bytes, str]): The packet payload
            source (Tuple[str, int]): Source address and port tuple
            destination (Optional[Tuple[str, int]]): Destination address and port tuple

        Returns:
            UDPPacket: New packet instance

        Raises:
            ValueError: If the input parameters are invalid
        """
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        
        return cls(
            payload=payload,
            source_addr=source[0],
            source_port=source[1],
            dest_addr=destination[0] if destination else None,
            dest_port=destination[1] if destination else None
        ) 