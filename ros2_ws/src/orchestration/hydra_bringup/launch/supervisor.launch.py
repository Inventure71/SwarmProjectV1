from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config_path = LaunchConfiguration("config_path")
    return LaunchDescription(
        [
            DeclareLaunchArgument("config_path", default_value=""),
            Node(
                package="hydra_supervisor_bridge",
                executable="supervisor_bridge",
                output="screen",
                parameters=[{"config_path": config_path}],
            ),
        ]
    )
