"""so101_bridge_node — hardware executor for a SO-101 arm via LeRobot.

Drop-in replacement for sim_robot_node: same topics, same Outcome message.
Only talks to hardware when the environment variable OL_ROBOT=so101 is set,
so launching the full stack by accident never moves a real arm.

Status: ALPHA. The LeRobot call-sites are isolated in `_connect` / `_move_ee`
/ `_grasp` so they can be filled in against your LeRobot version without
touching the ROS plumbing. Success/risk detection on real hardware is
currently: executed-without-exception + gripper-closed-on-object heuristic.
A proper outcome classifier (wrist camera + force) is on the roadmap.
"""
from __future__ import annotations

import os
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from operator_layer_core.types import ActionType, Outcome as CoreOutcome, RiskClass
from operator_layer_msgs.msg import Decision, Outcome, ProposedAction

from . import conversions as C

RELIABLE_LATCHED = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
RELIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class SO101BridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("so101_bridge")
        self.declare_parameter("port", "/dev/ttyACM0")
        self.declare_parameter("robot_id", "so101_follower")
        if os.environ.get("OL_ROBOT") != "so101":
            raise SystemExit("so101_bridge refuses to start without OL_ROBOT=so101 (safety interlock)")
        self.robot = self._connect(self.get_parameter("port").value, self.get_parameter("robot_id").value)
        self._actions: dict[str, ProposedAction] = {}
        self.pub = self.create_publisher(Outcome, "/operator_layer/outcome", RELIABLE_LATCHED)
        self.create_subscription(ProposedAction, "/operator_layer/proposed_action", self._cache, RELIABLE)
        self.create_subscription(Decision, "/operator_layer/decision", self.on_decision, RELIABLE_LATCHED)
        self.get_logger().warn("so101_bridge is LIVE — approved actions will move the arm")

    # ---------------------------------------------------------------- LeRobot call-sites
    def _connect(self, port: str, robot_id: str):
        try:
            from lerobot.robots.so101_follower import SO101Follower, SO101FollowerConfig  # type: ignore
        except ImportError as e:   # pragma: no cover
            raise SystemExit(f"lerobot not installed: {e}")
        robot = SO101Follower(SO101FollowerConfig(port=port, id=robot_id))
        robot.connect()
        return robot

    def _move_ee(self, xyz_yaw: list[float]) -> None:
        # TODO: IK -> joint targets -> robot.send_action({...}). Use operator_layer_core.sim.KinematicSO101Sim.ik_approx
        # as the IK until a calibrated solver is in place.
        raise NotImplementedError("fill in against your LeRobot version")

    def _grasp(self, close: bool) -> bool:
        raise NotImplementedError

    # ---------------------------------------------------------------- ROS plumbing
    def _cache(self, msg: ProposedAction) -> None:
        self._actions[msg.action_id] = msg

    def on_decision(self, msg: Decision) -> None:
        if msg.verdict != "approve":
            return
        raw = self._actions.pop(msg.action_id, None)
        if raw is None:
            return
        a = C.proposed_from_msg(raw)
        t0 = time.time()
        try:
            if a.action_type in (ActionType.MOVE_EE, ActionType.PICK_PLACE):
                self._move_ee(a.target)
                held = self._grasp(True) if a.action_type == ActionType.PICK_PLACE else True
                o = CoreOutcome(action_id=a.action_id, executed=True, success=held,
                                risk=RiskClass.NONE if held else RiskClass.OBJECT_DROP,
                                duration_s=time.time() - t0, robot="so101")
            else:
                o = CoreOutcome(action_id=a.action_id, executed=False, success=False, robot="so101")
        except Exception as e:   # noqa: BLE001 — any hardware fault is an outcome, not a crash
            self.get_logger().error(f"[{a.action_id}] hardware fault: {e}")
            o = CoreOutcome(action_id=a.action_id, executed=True, success=False,
                            duration_s=time.time() - t0, robot="so101")
        self.pub.publish(C.outcome_to_msg(o, time.time()))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SO101BridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
