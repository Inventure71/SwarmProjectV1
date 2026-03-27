from setuptools import find_packages, setup

package_name = "mosaic_robot_agent"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Mosaic",
    maintainer_email="dev@example.com",
    description="Mosaic robot-local ROS 2 execution agent.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "robot_agent = mosaic_robot_agent.agent_node:main",
        ],
    },
)
