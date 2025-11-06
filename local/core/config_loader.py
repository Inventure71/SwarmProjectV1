#!/usr/bin/env python3
"""
Configuration loader utility for robot swarm project.
Loads configuration from config.json and provides easy access to robot settings.
"""

import json
from pathlib import Path
from typing import Optional, Tuple


class ConfigLoader:
    """Singleton class to load and manage configuration."""

    _instance = None
    _config = None
    _config_path = None

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
        current_file = Path(__file__).resolve()
        # Look for config.json in the local directory (parent of core)
        local_dir = current_file.parent.parent
        config_path = local_dir / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")

        with open(config_path, 'r') as f:
            ConfigLoader._config = json.load(f)
        ConfigLoader._config_path = config_path

        print(f"[ConfigLoader] Configuration loaded from {config_path}")

    def _persist_config(self) -> None:
        """Persist the in-memory configuration back to disk."""
        if ConfigLoader._config_path is None:
            raise RuntimeError("Config path not initialised; call _load_config() first")

        with open(ConfigLoader._config_path, 'w') as f:
            json.dump(ConfigLoader._config, f, indent=2)
            f.write('\n')

        print(f"[ConfigLoader] Configuration saved to {ConfigLoader._config_path}")

    def reload(self) -> None:
        """Force reload configuration from disk."""
        ConfigLoader._config = None
        self._load_config()

    def get_robot_config(self):
        """
        Get the robot configuration mapping.

        Returns:
            dict: Dictionary mapping robot names to their configuration objects.
                  Example: {
                      'menelao': {
                          'name': 'menelao',
                          'umh_id': 'umh_0',
                          'type': 'real',
                          'cmd_vel_topic': '/menelao/cmd_vel'
                      }
                  }
        """
        return ConfigLoader._config.get('ROBOT_CONFIG', {})
    
    def get_robot_by_name(self, name: str):
        """
        Get configuration for a specific robot by name.
        
        Args:
            name: Robot name (e.g., 'menelao')

        Returns:
            dict | None: Robot configuration dictionary or None if not found.
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

    def get_hydra_config(self):
        """
        Get Hydra backend configuration.

        Returns:
            dict: Hydra configuration dictionary.
        """
        return ConfigLoader._config.get('HYDRA_CONFIG', {})

    def get_backend_endpoint(self) -> Tuple[str, int]:
        """Get backend host and port tuple for convenience."""
        hydra_cfg = self.get_hydra_config()
        return (
            hydra_cfg.get('backend_host', 'localhost'),
            int(hydra_cfg.get('backend_port', 9998)),
        )

    def get_pose_topic(self, robot_name: str) -> Optional[str]:
        """Compute pose topic for a robot from its UMH identifier."""
        robot = self.get_robot_by_name(robot_name)
        if not robot:
            return None

        pose_topic = robot.get('pose_topic')
        if pose_topic:
            return pose_topic

        umh_id = robot.get('umh_id')
        if not umh_id:
            return None

        return f"/natnet_ros/{umh_id}/pose"

    def get_cmd_vel_topic(self, robot_name: str) -> Optional[str]:
        """Return the cmd_vel topic for a robot if configured."""
        robot = self.get_robot_by_name(robot_name)
        if not robot:
            return None
        return robot.get('cmd_vel_topic')

    def upsert_robot(self, robot_name: str, robot_config: dict, persist: bool = True) -> None:
        """Add or update a robot configuration and optionally persist to disk."""
        ConfigLoader._config.setdefault('ROBOT_CONFIG', {})[robot_name] = robot_config
        if persist:
            self._persist_config()

    def remove_robot(self, robot_name: str, persist: bool = True) -> None:
        """Remove a robot from the configuration."""
        robots = ConfigLoader._config.setdefault('ROBOT_CONFIG', {})
        if robot_name in robots:
            del robots[robot_name]
            if persist:
                self._persist_config()


# Convenience function for getting config
def load_config():
    """
    Load and return the configuration.
    
    Returns:
        ConfigLoader: Configuration loader instance
    """
    return ConfigLoader()

