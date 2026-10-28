"""Gate + logger only — for plugging in your own policy and robot.

Your policy publishes ProposedAction on /operator_layer/proposed_action and
your robot (sim_robot or so101_bridge) subscribes to /operator_layer/decision.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    cfg = os.path.join(get_package_share_directory("operator_layer_ros"), "config", "gate.yaml")
    return LaunchDescription([
        Node(package="operator_layer_ros", executable="rehearsal_gate", parameters=[cfg], output="screen"),
        Node(package="operator_layer_ros", executable="outcome_logger", parameters=[cfg], output="screen"),
    ])
