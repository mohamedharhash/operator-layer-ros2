"""sim_robot_node — executes APPROVED actions in a simulated robot and reports Outcomes.

Subscribes:  /operator_layer/proposed_action   (ProposedAction)  -- cached by id
             /operator_layer/decision          (Decision)
Publishes:   /operator_layer/outcome           (Outcome)

Parameters:  robot_name, joint_noise_std, grasp_success_base, seed
  The noise parameters default to being *worse* than the rehearser's sim so
  the calibration report shows a non-zero sim-to-real gap out of the box.

To drive real hardware instead, run so101_bridge_node with OL_ROBOT=so101 in
place of this node; it consumes the same topics.
"""
from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from operator_layer_core import KinematicSO101Sim, SimExecutor, SO101Params
from operator_layer_msgs.msg import Decision, Outcome, ProposedAction

from . import conversions as C

RELIABLE_LATCHED = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
RELIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class SimRobotNode(Node):
    def __init__(self) -> None:
        super().__init__("sim_robot")
        self.declare_parameter("robot_name", "sim")
        self.declare_parameter("joint_noise_std", 0.012)
        self.declare_parameter("grasp_success_base", 0.85)
        self.declare_parameter("seed", -1)
        p = self.get_parameter
        seed = p("seed").value
        sim = KinematicSO101Sim(SO101Params(joint_noise_std=p("joint_noise_std").value,
                                            grasp_success_base=p("grasp_success_base").value))
        self.executor_ = SimExecutor(sim, name=p("robot_name").value, seed=None if seed < 0 else seed)
        self._actions: dict[str, ProposedAction] = {}

        self.pub = self.create_publisher(Outcome, "/operator_layer/outcome", RELIABLE_LATCHED)
        self.create_subscription(ProposedAction, "/operator_layer/proposed_action", self._cache, RELIABLE)
        self.create_subscription(Decision, "/operator_layer/decision", self.on_decision, RELIABLE_LATCHED)
        self.get_logger().info(f"sim robot '{self.executor_.name}' up")

    def _cache(self, msg: ProposedAction) -> None:
        self._actions[msg.action_id] = msg
        if len(self._actions) > 1000:                     # bounded cache
            self._actions.pop(next(iter(self._actions)))

    def on_decision(self, msg: Decision) -> None:
        if msg.verdict != "approve":
            return
        raw = self._actions.pop(msg.action_id, None)
        if raw is None:
            self.get_logger().warn(f"approved action {msg.action_id} not in cache; skipping")
            return
        action = C.proposed_from_msg(raw)
        outcome = self.executor_.execute(action)
        self.get_logger().info(f"[{action.action_id}] executed -> "
                               f"{'ok' if outcome.success else outcome.risk.value} err={outcome.final_error:.4f}")
        self.pub.publish(C.outcome_to_msg(outcome, time.time()))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SimRobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
