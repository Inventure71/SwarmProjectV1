from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "config" / "fleet.json").exists() and (parent / "ros2_ws").exists():
            return parent
    # Fallback for environments where config is not present yet.
    return current.parents[len(current.parents) - 1]


REPO_ROOT = _find_repo_root()
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "fleet.json"


@dataclass
class RobotConfig:
    name: str
    namespace: str
    robot_type: str
    umh_id: Optional[str]
    cmd_vel_topic: str
    color: str
    cmd_vel_msg_type: str = "twist"
    client_port: int = 0
    max_linear: float = 0.5
    max_angular: float = 1.5
    pose_topic: Optional[str] = None
    pose_flip_x: Optional[bool] = None
    battery_topic: Optional[str] = None
    imu_topic: Optional[str] = None
    odometry_topic: Optional[str] = None
    range_topics: Dict[str, str] = field(default_factory=dict)

    @property
    def is_dummy(self) -> bool:
        return self.robot_type == "dummy"

    def resolved_pose_topic(self) -> Optional[str]:
        if self.pose_topic:
            return self.pose_topic
        if self.umh_id:
            return f"/natnet_ros/{self.umh_id}/pose"
        return None

    def should_flip_pose_x(self) -> bool:
        """
        Return whether pose X should be mirrored into Mosaic's world frame.

        If not explicitly configured, default to True for natnet_ros topics to
        preserve legacy OptiTrack behavior.
        """
        if self.pose_flip_x is not None:
            return bool(self.pose_flip_x)
        topic = self.resolved_pose_topic() or ""
        return topic.startswith("/natnet_ros/")

    def uses_stamped_cmd_vel(self) -> bool:
        return self.cmd_vel_msg_type.strip().lower() in {"twiststamped", "twist_stamped", "stamped"}


@dataclass
class FleetConfig:
    robots: Dict[str, RobotConfig]
    mosaic_config: Dict[str, object]
    clients_config: Dict[str, object]

    def get_robot(self, name: str) -> Optional[RobotConfig]:
        return self.robots.get(name)

    def gamma_client_ips(self) -> list[str]:
        ips = self.clients_config.get("ips", [])
        return [str(ip) for ip in ips] if isinstance(ips, list) else []


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_fleet_config(config_path: str | Path | None = None) -> FleetConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    raw = _load_json(path)
    robots = {}
    for name, cfg in raw.get("ROBOT_CONFIG", {}).items():
        namespace = cfg.get("namespace") or f"/{name}"
        robots[name] = RobotConfig(
            name=name,
            namespace=namespace,
            robot_type=cfg.get("type", "real"),
            umh_id=cfg.get("umh_id"),
            cmd_vel_topic=cfg.get("cmd_vel_topic") or f"{namespace}/cmd_vel",
            cmd_vel_msg_type=str(cfg.get("cmd_vel_msg_type", "twist")),
            color=cfg.get("color", "#00aaff"),
            client_port=int(cfg.get("client_port", 0) or 0),
            max_linear=float(cfg.get("max_linear", raw.get("MOSAIC_CONFIG", {}).get("default_max_linear", 0.5))),
            max_angular=float(cfg.get("max_angular", raw.get("MOSAIC_CONFIG", {}).get("default_max_angular", 1.5))),
            pose_topic=cfg.get("pose_topic"),
            pose_flip_x=cfg.get("pose_flip_x"),
            battery_topic=cfg.get("battery_topic"),
            imu_topic=cfg.get("imu_topic"),
            odometry_topic=cfg.get("odometry_topic"),
            range_topics=dict(cfg.get("range_topics", {})),
        )
    return FleetConfig(
        robots=robots,
        mosaic_config=dict(raw.get("MOSAIC_CONFIG", {})),
        clients_config=dict(raw.get("CLIENTS_CONFIG", {})),
    )
