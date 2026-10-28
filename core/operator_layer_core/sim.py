"""Simulation backends for the rehearser.

The rehearser only depends on the `SimBackend` protocol, so a MuJoCo or
Gazebo backend can replace `KinematicSO101Sim` without touching the gate.

`KinematicSO101Sim` is deliberately lightweight: a 5-DOF planar-ish kinematic
chain with the approximate SO-101 link lengths, joint limits, actuator noise,
and a crude grasp model. It is NOT a physics engine. Its job is to make the
rehearsal distribution *behave* like a real one (stochastic, sensitive to
reach and joint limits, with distinct risk classes) so the gate, store, and
calibration machinery can be built and tested end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from .types import ActionType, ProposedAction, RiskClass, RolloutResult


class SimBackend(Protocol):
    name: str

    def rollout(self, action: ProposedAction, rng: np.random.Generator) -> RolloutResult: ...


@dataclass
class SO101Params:
    # Approximate link lengths (m) for a SO-101-class arm: shoulder, upper, fore, wrist
    links: tuple = (0.045, 0.115, 0.135, 0.06)
    # base yaw, shoulder pitch, elbow flex, wrist pitch, wrist roll (rad)
    joint_limits: tuple = ((-1.9, 1.9), (-1.9, 1.9), (-2.9, 2.9), (-1.9, 1.9), (-2.8, 2.8))
    reach_m: float = 0.31  # l1 + l2 + l3 fully extended
    # Noise models. These are the knobs that calibration data should tune.
    joint_noise_std: float = 0.008  # rad, per-joint actuation noise
    pose_noise_std: float = 0.003  # m, end-effector placement noise
    grasp_success_base: float = 0.98  # prob of a grasp holding when well-aligned
    grasp_align_tol_m: float = 0.025  # misalignment beyond this degrades grasp
    human_zone: tuple = field(
        default_factory=lambda: (0.15, -0.22, 0.05, 0.07)
    )  # x,y,z,radius: a person standing to the robot's right


class KinematicSO101Sim:
    name = "kinematic_so101"

    def __init__(self, params: SO101Params | None = None):
        self.p = params or SO101Params()

    # ------------------------------------------------------------------ kinematics
    def fk(self, q: np.ndarray) -> np.ndarray:
        """Forward kinematics: 5 joint angles -> (x, y, z) of the end effector."""
        l0, l1, l2, l3 = self.p.links
        base_yaw, shoulder, elbow, wrist, _ = q
        # planar chain in the arm plane, then rotated by base yaw
        r = (
            l1 * np.cos(shoulder)
            + l2 * np.cos(shoulder + elbow)
            + l3 * np.cos(shoulder + elbow + wrist)
        )
        z = (
            l0
            + l1 * np.sin(shoulder)
            + l2 * np.sin(shoulder + elbow)
            + l3 * np.sin(shoulder + elbow + wrist)
        )
        return np.array([r * np.cos(base_yaw), r * np.sin(base_yaw), z])

    def ik_approx(self, xyz: np.ndarray) -> np.ndarray | None:
        """Crude 2-link IK for the shoulder/elbow with wrist held level. Returns None if unreachable."""
        l0, l1, l2, l3 = self.p.links
        x, y, z = xyz
        yaw = np.arctan2(y, x)
        r = np.hypot(x, y) - l3  # wrist level => last link extends horizontally
        zz = z - l0
        d = np.hypot(r, zz)
        if d > (l1 + l2) or d < abs(l1 - l2):
            return None
        cos_e = (d**2 - l1**2 - l2**2) / (2 * l1 * l2)
        elbow = -np.arccos(np.clip(cos_e, -1, 1))
        shoulder = np.arctan2(zz, r) - np.arctan2(l2 * np.sin(elbow), l1 + l2 * np.cos(elbow))
        wrist = -(shoulder + elbow)
        return np.array([yaw, shoulder, elbow, wrist, 0.0])

    # ------------------------------------------------------------------ checks
    def _violates_limits(self, q: np.ndarray) -> bool:
        return any(not (lo <= qi <= hi) for qi, (lo, hi) in zip(q, self.p.joint_limits))

    def _near_human(self, xyz: np.ndarray) -> bool:
        hx, hy, hz, rad = self.p.human_zone
        return float(np.linalg.norm(xyz - np.array([hx, hy, hz]))) < rad

    # ------------------------------------------------------------------ rollout
    def rollout(self, action: ProposedAction, rng: np.random.Generator) -> RolloutResult:
        p = self.p
        t = float(rng.uniform(0.8, 1.6))

        if action.action_type == ActionType.MOVE_JOINTS:
            q_cmd = np.asarray(action.target, dtype=float)
            if q_cmd.shape != (5,):
                return RolloutResult(success=False, risk=RiskClass.WORKSPACE_LIMIT, duration_s=t)
            q = q_cmd + rng.normal(0, p.joint_noise_std, size=5)
            if self._violates_limits(q):
                return RolloutResult(success=False, risk=RiskClass.WORKSPACE_LIMIT, duration_s=t)
            ee = self.fk(q)
            if self._near_human(ee):
                return RolloutResult(success=False, risk=RiskClass.HUMAN_PROXIMITY, duration_s=t)
            err = float(np.linalg.norm(q - q_cmd))
            return RolloutResult(success=err < 0.05, final_error=err, duration_s=t)

        if action.action_type in (ActionType.MOVE_EE, ActionType.PICK_PLACE):
            goal = np.asarray(action.target[:3], dtype=float)
            if np.linalg.norm(goal[:2]) > p.reach_m or goal[2] < 0.0:
                return RolloutResult(success=False, risk=RiskClass.WORKSPACE_LIMIT, duration_s=t)
            q = self.ik_approx(goal)
            if q is None or self._violates_limits(q):
                return RolloutResult(success=False, risk=RiskClass.WORKSPACE_LIMIT, duration_s=t)
            if self._near_human(goal):
                return RolloutResult(success=False, risk=RiskClass.HUMAN_PROXIMITY, duration_s=t)
            # execute with actuation noise, then measure placement error
            q_noisy = q + rng.normal(0, p.joint_noise_std, size=5)
            ee = self.fk(q_noisy) + rng.normal(0, p.pose_noise_std, size=3)
            err = float(np.linalg.norm(ee - goal))
            # near the reach boundary, small joint noise => large tip error (lever arm)
            if action.action_type == ActionType.MOVE_EE:
                return RolloutResult(success=err < 0.01, final_error=err, duration_s=t)

            # PICK_PLACE: grasp model
            obj = np.asarray(action.context.get("object_xyz", goal), dtype=float)
            misalign = float(np.linalg.norm(ee - obj))
            p_hold = p.grasp_success_base * float(np.exp(-((misalign / p.grasp_align_tol_m) ** 2)))
            if rng.random() > p_hold:
                return RolloutResult(
                    success=False,
                    risk=RiskClass.OBJECT_DROP,
                    final_error=misalign,
                    duration_s=t * 2,
                )
            return RolloutResult(success=True, final_error=misalign, duration_s=t * 2)

        if action.action_type == ActionType.GRIPPER:
            return RolloutResult(success=True, duration_s=0.4)

        return RolloutResult(success=False, risk=RiskClass.WORKSPACE_LIMIT, duration_s=t)
