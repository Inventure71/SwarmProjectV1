#!/usr/bin/env python3
"""
Configuration loader utility for robot swarm project.
Loads configuration from config.json and provides easy access to robot settings.
"""

import json
from pathlib import Path


class ConfigLoader:
    """Singleton class to load and manage configuration."""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        """Ensure only one instance of ConfigLoader exists."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the config loader (loads config only once)."""
        if ConfigLoader._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load configuration from config.json file."""
        # Find the config.json file (assumes it's at project root)
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent  # Go up to project root
        config_path = project_root / "config.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")
        
        with open(config_path, 'r') as f:
            ConfigLoader._config = json.load(f)
        
        print(f"[ConfigLoader] Configuration loaded from {config_path}")
    
    def get_robot_config(self):
        """
        Get the robot configuration mapping.
        
        Returns:
            dict: Dictionary mapping robot names to their IP and port settings.
                  Example: {'umh_2': {'ip': '192.168.1.2', 'port': 9876}}
        """
        return ConfigLoader._config.get('ROBOT_CONFIG', {})
    
    def get_robot_by_name(self, name: str):
        """
        Get configuration for a specific robot by name.
        
        Args:
            name: Robot name (e.g., 'umh_2')
        
        Returns:
            dict: Robot configuration with 'ip' and 'port' keys, or None if not found.
        """
        robot_config = self.get_robot_config()
        return robot_config.get(name)
    
    def get_all_robot_names(self):
        """
        Get list of all configured robot names.
        
        Returns:
            list: List of robot names
        """
        return list(self.get_robot_config().keys())
    
    def get_config(self):
        """
        Get the entire configuration dictionary.
        
        Returns:
            dict: Full configuration
        """
        return ConfigLoader._config


# Convenience function for getting config
def load_config():
    """
    Load and return the configuration.
    
    Returns:
        ConfigLoader: Configuration loader instance
    """
    return ConfigLoader()

