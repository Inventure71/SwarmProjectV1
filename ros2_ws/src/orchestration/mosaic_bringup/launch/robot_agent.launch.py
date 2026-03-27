from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config_path = LaunchConfiguration("config_path")
    robot_name = LaunchConfiguration("robot_name")
    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_name"),
            DeclareLaunchArgument("config_path", default_value=""),
            Node(
                package="mosaic_robot_agent",
                executable="robot_agent",
                output="screen",
                parameters=[{"robot_name": robot_name, "config_path": config_path}],
            ),
        ]
    )
