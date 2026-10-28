"""scripted_policy_node — stand-in for a learned policy. Proposes pick-and-place
actions across the workspace at a fixed rate (some easy, some at the reach
limit, some inside the human zone). Replace with your ACT / Diffusion / VLA
policy: anything that publishes ProposedAction works.

Publishes:  /operator_layer/proposed_action
Parameters: rate_hz, max_actions (-1 = forever), seed
"""
from __future__ import annotations

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from operator_layer_core.types import ActionType, ProposedAction as CoreProposed
from operator_layer_msgs.msg import ProposedAction

from . import conversions as C

RELIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class ScriptedPolicyNode(Node):
    def __init__(self) -> None:
        super().__init__("scripted_policy")
        self.declare_parameter("rate_hz", 2.0)
        self.declare_parameter("max_actions", -1)
        self.declare_parameter("seed", 0)
        self.rng = np.random.default_rng(self.get_parameter("seed").value)
        self.max_actions = self.get_parameter("max_actions").value
        self.i = 0
        self.pub = self.create_publisher(ProposedAction, "/operator_layer/proposed_action", RELIABLE)
        self.create_timer(1.0 / self.get_parameter("rate_hz").value, self.tick)

    def tick(self) -> None:
        if 0 <= self.max_actions <= self.i:
            return
        # Don't publish into the void: wait until at least one subscriber (the gate)
        # has been discovered, otherwise the first message is lost on DDS startup.
        if self.pub.get_subscription_count() == 0:
            return
        if self.i % 10 == 7:
            goal = [0.15, -0.22, 0.05]                     # inside the human zone
        else:
            r, th = self.rng.uniform(0.12, 0.30), self.rng.uniform(-1.2, 1.2)
            goal = [float(r * np.cos(th)), float(r * np.sin(th)), float(self.rng.uniform(0.02, 0.12))]
        obj = [float(x) for x in np.asarray(goal) + self.rng.normal(0, 0.004, 3)]
        a = CoreProposed(source="scripted_v1", action_type=ActionType.PICK_PLACE,
                         target=goal + [0.0], context={"object_xyz": obj})
        self.pub.publish(C.proposed_to_msg(a))
        self.i += 1


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScriptedPolicyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
