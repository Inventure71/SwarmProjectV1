from setuptools import find_packages, setup

package_name = "mosaic_optitrack_bridge"

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
    description="Optional Mosaic OptiTrack relay bridge for ROS 2 pose topics.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "optitrack_bridge = mosaic_optitrack_bridge.bridge_node:main",
        ],
    },
)
