from setuptools import setup

package_name = "hydra_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/supervisor.launch.py", "launch/robot_agent.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Hydra",
    maintainer_email="dev@example.com",
    description="Launch files for the Hydra ROS 2 stack.",
    license="MIT",
)
