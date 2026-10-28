"""Full loop in simulation: scripted policy -> gate -> auto operator -> sim robot -> logger.

    ros2 launch operator_layer_ros sim.launch.py
    ros2 launch operator_layer_ros sim.launch.py max_actions:=100 store_path:=data/run1.jsonl
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    cfg = os.path.join(get_package_share_directory("operator_layer_ros"), "config", "gate.yaml")
    max_actions = LaunchConfiguration("max_actions")
    store_path = LaunchConfiguration("store_path")
    return LaunchDescription([
        DeclareLaunchArgument("max_actions", default_value="-1"),
        DeclareLaunchArgument("store_path", default_value="data/episodes.jsonl"),
        Node(package="operator_layer_ros", executable="rehearsal_gate", name="rehearsal_gate",
             parameters=[cfg], output="screen"),
        Node(package="operator_layer_ros", executable="auto_operator", name="auto_operator",
             parameters=[cfg], output="screen"),
        Node(package="operator_layer_ros", executable="sim_robot", name="sim_robot",
             parameters=[cfg], output="screen"),
        Node(package="operator_layer_ros", executable="outcome_logger", name="outcome_logger",
             parameters=[cfg, {"store_path": store_path}], output="screen"),
        Node(package="operator_layer_ros", executable="scripted_policy", name="scripted_policy",
             parameters=[cfg, {"max_actions": max_actions}], output="screen"),
    ])
