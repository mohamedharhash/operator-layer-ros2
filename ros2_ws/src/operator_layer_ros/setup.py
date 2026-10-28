import os
from glob import glob

from setuptools import find_packages, setup

package_name = "operator_layer_ros"

setup(
    name=package_name,
    version="0.2.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools", "operator-layer-core"],
    zip_safe=True,
    maintainer="Mohamed Harhash",
    maintainer_email="mohamedharhash98@gmail.com",
    description="ROS 2 nodes for the Operator Layer rehearse-before-execute gate.",
    license="MIT",
    # colcon reads this to decide to run pytest (see colcon_core package_augmentation/python.py)
    extras_require={"test": ["pytest"]},
    entry_points={
        "console_scripts": [
            "rehearsal_gate = operator_layer_ros.rehearsal_gate_node:main",
            "sim_robot = operator_layer_ros.sim_robot_node:main",
            "outcome_logger = operator_layer_ros.outcome_logger_node:main",
            "auto_operator = operator_layer_ros.auto_operator_node:main",
            "scripted_policy = operator_layer_ros.scripted_policy_node:main",
            "so101_bridge = operator_layer_ros.so101_bridge_node:main",
        ],
    },
)
