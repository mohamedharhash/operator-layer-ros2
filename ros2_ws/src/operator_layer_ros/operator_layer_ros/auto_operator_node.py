"""auto_operator_node — stands in for a human on ASK_OPERATOR.

Subscribes:  /operator_layer/rehearsal_result
Publishes:   /operator_layer/operator_decision

It only answers rehearsals that fall in the gate's grey zone (it mirrors the
gate's thresholds via parameters so it doesn't double-decide), approving when
p_success >= approve_if_above. Replace with a real console for human review.
"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from operator_layer_core.types import Decision as CoreDecision, Verdict
from operator_layer_msgs.msg import Decision, RehearsalResult

from . import conversions as C

RELIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class AutoOperatorNode(Node):
    def __init__(self) -> None:
        super().__init__("auto_operator")
        self.declare_parameter("operator_id", "auto_operator")
        self.declare_parameter("approve_if_above", 0.85)
        self.declare_parameter("gate_approve_threshold", 0.95)
        self.declare_parameter("gate_reject_threshold", 0.60)
        self.declare_parameter("gate_max_risk", 0.05)
        self.declare_parameter("hard_risks", ["human_proximity"])
        p = self.get_parameter
        self.oid, self.thr = p("operator_id").value, p("approve_if_above").value
        self.g_app, self.g_rej, self.g_risk = (p("gate_approve_threshold").value,
                                               p("gate_reject_threshold").value, p("gate_max_risk").value)
        self.hard = set(p("hard_risks").value)
        self.pub = self.create_publisher(Decision, "/operator_layer/operator_decision", RELIABLE)
        self.create_subscription(RehearsalResult, "/operator_layer/rehearsal_result", self.on_rehearsal, RELIABLE)

    def _is_grey_zone(self, r) -> bool:
        if any(r.risk_histogram.get(h, 0) > 0 for h in self.hard):
            return False
        if r.p_success >= self.g_app and r.p_risk <= self.g_risk:
            return False
        return r.p_success >= self.g_rej

    def on_rehearsal(self, m: RehearsalResult) -> None:
        r = C.rehearsal_from_msg(m)
        if not self._is_grey_zone(r):
            return
        ok = r.p_success >= self.thr
        d = CoreDecision(action_id=r.action_id, verdict=Verdict.APPROVE if ok else Verdict.REJECT,
                         decided_by=self.oid,
                         reason=f"{'approved' if ok else 'declined'} at p_success={r.p_success:.2f}")
        self.get_logger().info(f"[{r.action_id}] {d.reason}")
        self.pub.publish(C.decision_to_msg(d))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AutoOperatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
