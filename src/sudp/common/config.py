#!/usr/bin/env python3
"""Configuration management for SUDP.

This module handles:
- YAML configuration file loading
- Merging command line arguments with YAML config
- Configuration validation
- Instance-specific configuration
"""

import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
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
    instance_name: str = "default"
    instance_dir: Optional[str] = None

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
    instance_name: str = "default"
    instance_dir: Optional[str] = None

def get_instance_dir(instance_name: str) -> Path:
    """Get the directory for an instance.
    
    Args:
        instance_name: Name of the instance
        
    Returns:
        Path to the instance directory
    """
    base_dir = Path.home() / '.local/var/sudp'
    instance_dir = base_dir / instance_name
    instance_dir.mkdir(parents=True, exist_ok=True)
    return instance_dir

def get_instance_config_path(instance_name: str) -> Path:
    """Get the configuration file path for an instance.
    
    Args:
        instance_name: Name of the instance
        
    Returns:
        Path to the instance configuration file
    """
    base_dir = Path.home() / '.config/sudp'
    base_dir.mkdir(parents=True, exist_ok=True)
    
    if instance_name == "default":
        return base_dir / "server.yaml"
    else:
        return base_dir / f"server_{instance_name}.yaml"

def list_instances() -> List[str]:
    """List all available instances.
    
    Returns:
        List of instance names
    """
    instances = ["default"]
    config_dir = Path.home() / '.config/sudp'
    
    if config_dir.exists():
        for file in config_dir.glob("server_*.yaml"):
            instance_name = file.name.replace("server_", "").replace(".yaml", "")
            instances.append(instance_name)
    
    # Also check for running instances in the var directory
    var_dir = Path.home() / '.local/var/sudp'
    if var_dir.exists():
        for dir_path in var_dir.iterdir():
            if dir_path.is_dir() and dir_path.name not in instances:
                instances.append(dir_path.name)
    
    return sorted(instances)

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
    
    # Get instance name
    instance_name = args_dict.get("instance_name", "default") if args else "default"
    
    # Merge configs
    config = merge_config(yaml_config, args_dict)
    
    # Set instance name and directory
    config["instance_name"] = instance_name
    if "instance_dir" not in config or not config["instance_dir"]:
        config["instance_dir"] = str(get_instance_dir(instance_name))
    
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
    
    # Get instance name
    instance_name = args_dict.get("instance_name", "default")
    
    # Merge configs
    config = merge_config(yaml_config, args_dict)
    
    # Set instance name and directory
    config["instance_name"] = instance_name
    if "instance_dir" not in config or not config["instance_dir"]:
        config["instance_dir"] = str(get_instance_dir(instance_name))
    
    # Create ClientConfig with merged values
    return ClientConfig(**config) 