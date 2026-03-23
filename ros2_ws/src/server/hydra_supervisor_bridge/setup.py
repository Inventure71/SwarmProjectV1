from setuptools import find_packages, setup

package_name = "hydra_supervisor_bridge"

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
    maintainer="Hydra",
    maintainer_email="dev@example.com",
    description="Hydra ROS 2 supervisor bridge for UI and Gama UDP compatibility.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "supervisor_bridge = hydra_supervisor_bridge.bridge_node:main",
        ],
    },
)
