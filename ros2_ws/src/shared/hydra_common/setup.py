from setuptools import find_packages, setup

package_name = "hydra_common"

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
    description="Shared Python utilities for the Hydra ROS 2 stack.",
    license="MIT",
)
