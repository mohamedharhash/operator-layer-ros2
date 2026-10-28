"""rehearsal_gate_node

Subscribes:  /operator_layer/proposed_action      (ProposedAction)
             /operator_layer/operator_decision    (Decision)   -- a human answering ASK_OPERATOR
Publishes:   /operator_layer/rehearsal_result     (RehearsalResult)
             /operator_layer/decision             (Decision)   -- the final verdict, approve/reject only

Parameters:  n_rollouts, approve_threshold, reject_threshold, max_risk, hard_risks,
             keep_rollouts, operator_timeout_s, seed

Flow per action:
  proposed -> rehearse N times -> gate.decide
     APPROVE/REJECT  -> publish decision immediately
     ASK_OPERATOR    -> publish rehearsal (already done) and wait up to operator_timeout_s
                        for a Decision on /operator_decision with the same action_id;
                        on timeout -> REJECT ("operator timeout")

Design notes:
  * All logic is in operator_layer_core; this node is a translator + a timer.
  * Decisions use RELIABLE + TRANSIENT_LOCAL QoS so a logger that starts late
    still receives them. Rehearsal results are RELIABLE but VOLATILE (large, frequent).
"""
from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from operator_layer_core import GatePolicy, KinematicSO101Sim, Rehearser, RiskClass, Verdict
from operator_layer_core.types import Decision as CoreDecision
from operator_layer_msgs.msg import Decision, ProposedAction, RehearsalResult

from . import conversions as C

RELIABLE_LATCHED = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
RELIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class RehearsalGateNode(Node):
    def __init__(self) -> None:
        super().__init__("rehearsal_gate")
        self.declare_parameter("n_rollouts", 50)
        self.declare_parameter("approve_threshold", 0.95)
        self.declare_parameter("reject_threshold", 0.60)
        self.declare_parameter("max_risk", 0.05)
        self.declare_parameter("hard_risks", ["human_proximity"])
        self.declare_parameter("keep_rollouts", False)
        self.declare_parameter("operator_timeout_s", 30.0)
        self.declare_parameter("seed", -1)
        self.declare_parameter("sim_backend", "kinematic_so101")

        p = self.get_parameter
        seed = p("seed").value
        backend = self._make_backend(p("sim_backend").value)
        self.rehearser = Rehearser(backend, n_rollouts=p("n_rollouts").value,
                                   seed=None if seed < 0 else seed, keep_rollouts=p("keep_rollouts").value)
        self.gate = GatePolicy(approve_threshold=p("approve_threshold").value,
                               reject_threshold=p("reject_threshold").value,
                               max_risk=p("max_risk").value,
                               hard_risks={RiskClass(r) for r in p("hard_risks").value})
        self.operator_timeout = p("operator_timeout_s").value
        self._awaiting: dict[str, float] = {}   # action_id -> deadline

        self.pub_rehearsal = self.create_publisher(RehearsalResult, "/operator_layer/rehearsal_result", RELIABLE)
        self.pub_decision = self.create_publisher(Decision, "/operator_layer/decision", RELIABLE_LATCHED)
        self.create_subscription(ProposedAction, "/operator_layer/proposed_action", self.on_proposed, RELIABLE)
        self.create_subscription(Decision, "/operator_layer/operator_decision", self.on_operator_decision, RELIABLE)
        self.create_timer(0.5, self._expire_waits)
        self.get_logger().info(f"gate up: backend={backend.name} n={self.rehearser.n} "
                               f"approve>={self.gate.approve_threshold} reject<{self.gate.reject_threshold} "
                               f"max_risk={self.gate.max_risk} hard={[r.value for r in self.gate.hard_risks]}")

    @staticmethod
    def _make_backend(name: str):
        if name == "kinematic_so101":
            return KinematicSO101Sim()
        # Hook for a MuJoCo/Gazebo backend; keep the import lazy so the node runs without it.
        raise ValueError(f"unknown sim_backend {name!r}")

    # ------------------------------------------------------------------ callbacks
    def on_proposed(self, msg: ProposedAction) -> None:
        action = C.proposed_from_msg(msg)
        t0 = time.perf_counter()
        rehearsal = self.rehearser.rehearse(action)
        dt_ms = (time.perf_counter() - t0) * 1e3
        self.pub_rehearsal.publish(C.rehearsal_to_msg(rehearsal, time.time()))

        decision = self.gate.decide(rehearsal)
        self.get_logger().info(f"[{action.action_id}] {action.action_type.value} p_succ={rehearsal.p_success:.2f} "
                               f"p_risk={rehearsal.p_risk:.2f} -> {decision.verdict.value} ({dt_ms:.0f} ms)")
        if decision.verdict == Verdict.ASK_OPERATOR:
            self._awaiting[action.action_id] = time.time() + self.operator_timeout
            return   # the rehearsal result already went out; the operator answers on /operator_decision
        self.pub_decision.publish(C.decision_to_msg(decision))

    def on_operator_decision(self, msg: Decision) -> None:
        if msg.action_id not in self._awaiting:
            self.get_logger().warn(f"operator decision for unknown/expired action {msg.action_id}; ignoring")
            return
        del self._awaiting[msg.action_id]
        d = C.decision_from_msg(msg)
        if d.verdict == Verdict.ASK_OPERATOR:      # an operator can't punt back to the operator
            d = CoreDecision(action_id=d.action_id, verdict=Verdict.REJECT, decided_by=d.decided_by,
                             reason="operator returned ask_operator; treated as reject")
        self.get_logger().info(f"[{d.action_id}] operator {d.decided_by}: {d.verdict.value}")
        self.pub_decision.publish(C.decision_to_msg(d))

    def _expire_waits(self) -> None:
        now = time.time()
        for aid, deadline in list(self._awaiting.items()):
            if now >= deadline:
                del self._awaiting[aid]
                d = CoreDecision(action_id=aid, verdict=Verdict.REJECT, decided_by="auto_policy",
                                 reason=f"operator timeout after {self.operator_timeout:.0f}s")
                self.get_logger().warn(f"[{aid}] {d.reason}")
                self.pub_decision.publish(C.decision_to_msg(d))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RehearsalGateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
