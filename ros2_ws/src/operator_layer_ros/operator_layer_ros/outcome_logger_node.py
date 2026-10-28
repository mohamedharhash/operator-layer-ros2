"""outcome_logger_node — assembles EpisodeRecords and writes the episode store.

Subscribes:  /operator_layer/proposed_action, /rehearsal_result, /decision, /outcome
Publishes:   nothing (writes data/episodes.jsonl); logs a calibration summary every
             `report_every` closed episodes.

Parameters:  store_path, report_every
"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from operator_layer_core import EpisodeStore, calibrate
from operator_layer_core.types import EpisodeRecord
from operator_layer_msgs.msg import Decision, Outcome, ProposedAction, RehearsalResult

from . import conversions as C

RELIABLE_LATCHED = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
RELIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class OutcomeLoggerNode(Node):
    def __init__(self) -> None:
        super().__init__("outcome_logger")
        self.declare_parameter("store_path", "data/episodes.jsonl")
        self.declare_parameter("report_every", 20)
        self.store = EpisodeStore(self.get_parameter("store_path").value)
        self.report_every = self.get_parameter("report_every").value
        self._proposed, self._rehearsal = {}, {}
        self._closed = 0

        self.create_subscription(ProposedAction, "/operator_layer/proposed_action", self.on_proposed, RELIABLE)
        self.create_subscription(RehearsalResult, "/operator_layer/rehearsal_result", self.on_rehearsal, RELIABLE)
        self.create_subscription(Decision, "/operator_layer/decision", self.on_decision, RELIABLE_LATCHED)
        self.create_subscription(Outcome, "/operator_layer/outcome", self.on_outcome, RELIABLE_LATCHED)
        self.get_logger().info(f"logging episodes to {self.store.path}")

    def on_proposed(self, m: ProposedAction) -> None:
        self._proposed[m.action_id] = C.proposed_from_msg(m)

    def on_rehearsal(self, m: RehearsalResult) -> None:
        self._rehearsal[m.action_id] = C.rehearsal_from_msg(m)

    def on_decision(self, m: Decision) -> None:
        a, r = self._proposed.pop(m.action_id, None), self._rehearsal.pop(m.action_id, None)
        if a is None or r is None:
            self.get_logger().warn(f"decision for {m.action_id} without proposed/rehearsal; dropping")
            return
        self.store.open(EpisodeRecord(proposed=a, rehearsal=r, decision=C.decision_from_msg(m)))

    def on_outcome(self, m: Outcome) -> None:
        rec = self.store.close(C.outcome_from_msg(m))
        if rec is None:
            self.get_logger().warn(f"outcome for {m.action_id} with no open episode")
            return
        self._closed += 1
        if self._closed % self.report_every == 0:
            self.get_logger().info("\n" + calibrate(self.store).summary())


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OutcomeLoggerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("\n" + calibrate(node.store).summary())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
