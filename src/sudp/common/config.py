#!/usr/bin/env python3
"""Configuration management for SUDP.

This module handles:
- YAML configuration file loading
- Merging command line arguments with YAML config
- Configuration validation
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Server configuration parameters."""
    host: str = "127.0.0.1"
    port: int = 11223
    max_clients: int = 100
    log_dir: Optional[str] = None
    log_level: str = "INFO"
    enable_file_logging: bool = False
    enable_console_logging: bool = True

@dataclass
class ClientConfig:
    """Client configuration parameters."""
    udp_host: str = "127.0.0.1"
    udp_port: int = 1234
    server_host: str = "127.0.0.1"
    server_port: int = 11223
    buffer_size: int = 65507
    log_dir: Optional[str] = None
    log_level: str = "INFO"
    enable_file_logging: bool = False
    enable_console_logging: bool = True

def load_yaml_config(config_path: Optional[str]) -> Dict[str, Any]:
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Dict containing configuration values
    """
    if not config_path:
        return {}
        
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return {}
            
        with open(config_file) as f:
            return yaml.safe_load(f) or {}
            
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        return {}

def merge_config(yaml_config: Dict[str, Any], args_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Merge YAML config with command line arguments.
    
    Command line arguments take precedence over YAML config.
    
    Args:
        yaml_config: Configuration from YAML file
        args_dict: Configuration from command line args
        
    Returns:
        Merged configuration dictionary
    """
    # Start with YAML config
    config = yaml_config.copy()
    
    # Override with command line args (only if not None)
    for key, value in args_dict.items():
        if value is not None:
            config[key] = value
            
    return config

def create_server_config(yaml_path: Optional[str], args: Optional[Any] = None) -> ServerConfig:
    """Create server configuration from YAML and command line args.
    
    Args:
        yaml_path: Path to YAML configuration file
        args: Command line arguments (optional)
        
    Returns:
        ServerConfig instance
    """
    # Load YAML config
    yaml_config = load_yaml_config(yaml_path)
    
    # Convert args to dict if provided
    args_dict = vars(args) if args else {}
    
    # Merge configs
    config = merge_config(yaml_config, args_dict)
    
    # Create ServerConfig instance
    return ServerConfig(**config)

def create_client_config(yaml_path: Optional[str], args: Any) -> ClientConfig:
    """Create client configuration from YAML and command line args.
    
    Args:
        yaml_path: Path to YAML config file
        args: Parsed command line arguments
        
    Returns:
        ClientConfig instance
    """
    # Load YAML config
    yaml_config = load_yaml_config(yaml_path)
    
    # Convert args to dict, excluding config_file
    args_dict = {k: v for k, v in vars(args).items() 
                if k != 'config_file' and v is not None}
    
    # Merge configs
    config = merge_config(yaml_config, args_dict)
    
    # Create ClientConfig with merged values
    return ClientConfig(**config) 