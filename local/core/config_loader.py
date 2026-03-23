#!/usr/bin/env python3
"""
Configuration loader utility for robot swarm project.
Loads configuration from config.json and provides easy access to robot settings.
"""

import json
from pathlib import Path
from typing import Optional, Tuple
import colorsys


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
        local_dir = current_file.parent.parent
        shared_config_path = local_dir.parent / "config" / "fleet.json"
        config_path = shared_config_path if shared_config_path.exists() else local_dir / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")

        with open(config_path, 'r') as f:
            ConfigLoader._config = json.load(f)
        ConfigLoader._config_path = config_path

        print(f"[ConfigLoader] Configuration loaded from {config_path}")
        # Ensure robots have distinct colors assigned
        self._ensure_robot_colors()

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return (0, 0, 0)

    def _rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        r, g, b = rgb
        return f"#{r:02x}{g:02x}{b:02x}"

    def _is_distinct(self, rgb: Tuple[int, int, int], existing_rgbs: list[Tuple[int, int, int]], threshold: float = 110.0) -> bool:
        for er, eg, eb in existing_rgbs:
            dr = rgb[0] - er
            dg = rgb[1] - eg
            db = rgb[2] - eb
            if (dr*dr + dg*dg + db*db) ** 0.5 < threshold:
                return False
        return True

    def _generate_distinct_color(self, existing_hex: list[str], attempt_seed: int = 0) -> str:
        existing_rgbs = [self._hex_to_rgb(c) for c in existing_hex if isinstance(c, str) and c]
        # Use golden ratio conjugate to distribute hues
        phi = 0.61803398875
        hue = (0.11 + (len(existing_rgbs) + attempt_seed) * phi) % 1.0
        # Prefer vivid, not too light/dark
        s = 0.80
        v = 0.92
        r, g, b = colorsys.hsv_to_rgb(hue, s, v)
        rgb = (int(r * 255), int(g * 255), int(b * 255))
        # If too close to existing, nudge hue
        tries = 0
        while not self._is_distinct(rgb, existing_rgbs) and tries < 12:
            hue = (hue + 0.12) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, s, v)
            rgb = (int(r * 255), int(g * 255), int(b * 255))
            tries += 1
        return self._rgb_to_hex(rgb)

    def _ensure_robot_colors(self) -> None:
        robots = ConfigLoader._config.setdefault('ROBOT_CONFIG', {})
        changed = False
        existing_colors: list[str] = []
        # Collect already valid colors
        for rname, rcfg in robots.items():
            color = rcfg.get('color')
            if isinstance(color, str) and len(color) in (4, 7) and color.startswith('#'):
                existing_colors.append(color)
        # Assign colors to those missing
        for rname, rcfg in robots.items():
            color = rcfg.get('color')
            if not (isinstance(color, str) and len(color) in (4, 7) and color.startswith('#')):
                new_color = self._generate_distinct_color(existing_colors)
                rcfg['color'] = new_color
                existing_colors.append(new_color)
                changed = True
        if changed:
            self._persist_config()

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
        Get Hydra supervisor bridge configuration.

        Returns:
            dict: Hydra configuration dictionary.
        """
        return ConfigLoader._config.get('HYDRA_CONFIG', {})

    def get_supervisor_endpoint(self) -> Tuple[str, int]:
        """Get supervisor bridge host and port tuple for convenience."""
        hydra_cfg = self.get_hydra_config()
        return (
            hydra_cfg.get('supervisor_host', 'localhost'),
            int(hydra_cfg.get('supervisor_port', 9998)),
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
        robots = ConfigLoader._config.setdefault('ROBOT_CONFIG', {})
        # Ensure color assignment on insert/update
        if 'color' not in robot_config or not robot_config['color']:
            # Use currently assigned colors to pick a distinct one
            existing = [cfg.get('color') for cfg in robots.values() if isinstance(cfg.get('color'), str)]
            robot_config['color'] = self._generate_distinct_color(existing)
        robots[robot_name] = robot_config
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
