"""Integration test: launch the full sim loop and assert the pipeline closes episodes.

This is the "automated integration test for simulation" — it runs the real
nodes over real DDS topics under `colcon test`, with a bounded number of
actions, and checks that approved actions produce Outcomes and that the
logger wrote a non-empty episode store.
"""
import json
import os
import tempfile
import time
import unittest

import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from operator_layer_msgs.msg import Decision, Outcome

STORE = os.path.join(tempfile.mkdtemp(), "episodes.jsonl")
N_ACTIONS = 30


@pytest.mark.launch_test
def generate_test_description():
    cfg = os.path.join(get_package_share_directory("operator_layer_ros"), "config", "gate.yaml")
    common = dict(package="operator_layer_ros", parameters=[cfg], output="screen")
    nodes = [
        launch_ros.actions.Node(executable="rehearsal_gate", name="rehearsal_gate",
                                parameters=[cfg, {"seed": 1, "operator_timeout_s": 5.0}], package="operator_layer_ros", output="screen"),
        launch_ros.actions.Node(executable="auto_operator", name="auto_operator", **common),
        launch_ros.actions.Node(executable="sim_robot", name="sim_robot",
                                parameters=[cfg, {"seed": 2}], package="operator_layer_ros", output="screen"),
        launch_ros.actions.Node(executable="outcome_logger", name="outcome_logger",
                                parameters=[cfg, {"store_path": STORE}], package="operator_layer_ros", output="screen"),
        launch_ros.actions.Node(executable="scripted_policy", name="scripted_policy",
                                parameters=[cfg, {"max_actions": N_ACTIONS, "rate_hz": 5.0}], package="operator_layer_ros", output="screen"),
    ]
    return launch.LaunchDescription(nodes + [launch_testing.actions.ReadyToTest()]), {}


class TestSimLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.node = rclpy.create_node("sim_loop_probe")
        latched = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        cls.decisions, cls.outcomes = [], []
        cls.node.create_subscription(Decision, "/operator_layer/decision", cls.decisions.append, latched)
        cls.node.create_subscription(Outcome, "/operator_layer/outcome", cls.outcomes.append, latched)

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown()

    def test_every_action_gets_a_decision_and_approvals_get_outcomes(self):
        deadline = time.time() + 40
        while time.time() < deadline and len(self.decisions) < N_ACTIONS:
            rclpy.spin_once(self.node, timeout_sec=0.2)
        self.assertEqual(len(self.decisions), N_ACTIONS, "not every proposed action was decided")
        approved = {d.action_id for d in self.decisions if d.verdict == "approve"}
        self.assertGreater(len(approved), 0, "nothing was approved; gate or sim misconfigured")

        deadline = time.time() + 10
        while time.time() < deadline and len(self.outcomes) < len(approved):
            rclpy.spin_once(self.node, timeout_sec=0.2)
        self.assertEqual({o.action_id for o in self.outcomes}, approved)
        self.assertTrue(any(d.verdict == "reject" and "human_proximity" in d.reason for d in self.decisions),
                        "hard-risk rejection path never exercised")

    def test_episode_store_written(self):
        time.sleep(1.0)   # let the logger flush
        with open(STORE) as f:
            rows = [json.loads(l) for l in f if l.strip()]
        self.assertGreaterEqual(len(rows), 1)
        closed = [r for r in rows if r["outcome"] is not None]
        self.assertGreater(len(closed), 0)
        self.assertIn("p_success", closed[0]["rehearsal"])
