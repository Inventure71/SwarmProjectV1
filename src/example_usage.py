#!/usr/bin/env python3
"""
Example usage of the modular robot controller.
"""

from robot_controller_app import RobotControllerApp

def main():
    """Run the robot controller with default settings."""
    # You can specify a different robot name as an argument
    # app = RobotControllerApp(robot_name='umh_2')
    app = RobotControllerApp(robot_name='umh_5')
    app.run()

if __name__ == '__main__':
    main()

