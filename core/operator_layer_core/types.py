"""Core data types.

These mirror the ROS 2 messages in `operator_layer_msgs` one-to-one, so the
ROS nodes are thin translators and all logic lives here, testable without ROS.

Lifecycle of one action:

    ProposedAction --rehearse--> RehearsalResult --decide--> Decision
                                                                 |
                                                     (robot executes)
                                                                 v
                                                             Outcome
                                                                 |
                                                   EpisodeRecord = all four, scored
"""

from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    MOVE_JOINTS = "move_joints"  # target joint angles (rad)
    MOVE_EE = "move_ee"  # target end-effector pose (x, y, z, in metres; yaw)
    GRIPPER = "gripper"  # open/close
    PICK_PLACE = "pick_place"  # composite: approach, grasp, lift, place


class ProposedAction(BaseModel):
    """What a policy / planner / VLA wants the robot to do next."""

    action_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    stamp: float = Field(default_factory=time.time)
    source: str = "unknown"  # e.g. "act_policy_v3", "teleop", "scripted"
    action_type: ActionType
    target: list[float]  # meaning depends on action_type
    context: dict = Field(default_factory=dict)  # scene info the sim needs (object pose, etc.)


class RiskClass(str, Enum):
    NONE = "none"
    SELF_COLLISION = "self_collision"
    WORKSPACE_LIMIT = "workspace_limit"
    OBJECT_DROP = "object_drop"
    HUMAN_PROXIMITY = "human_proximity"


class RolloutResult(BaseModel):
    """One simulated attempt at the action."""

    success: bool
    risk: RiskClass = RiskClass.NONE
    final_error: float = 0.0  # distance from goal at end of rollout (m or rad)
    duration_s: float = 0.0


class RehearsalResult(BaseModel):
    """The distribution over N rollouts. This is what the operator sees."""

    action_id: str
    n_rollouts: int
    p_success: float  # fraction of rollouts that succeeded
    p_risk: float  # fraction with any risk event
    risk_histogram: dict[str, int]  # RiskClass -> count
    mean_final_error: float
    sim_backend: str
    rollouts: list[RolloutResult] = Field(default_factory=list)


class Verdict(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ASK_OPERATOR = "ask_operator"


class Decision(BaseModel):
    action_id: str
    verdict: Verdict
    decided_by: str  # "auto_policy" or an operator id
    reason: str
    stamp: float = Field(default_factory=time.time)


class Outcome(BaseModel):
    """What the real (or sim) robot actually did after an APPROVE."""

    action_id: str
    executed: bool
    success: bool
    risk: RiskClass = RiskClass.NONE
    final_error: float = 0.0
    duration_s: float = 0.0
    robot: str = "sim"


class EpisodeRecord(BaseModel):
    """One complete row in the episode store."""

    proposed: ProposedAction
    rehearsal: RehearsalResult
    decision: Decision
    outcome: Outcome | None = None

    @property
    def prediction_error(self) -> float | None:
        """|p_success - actual|; the per-episode calibration signal."""
        if self.outcome is None or not self.outcome.executed:
            return None
        return abs(self.rehearsal.p_success - (1.0 if self.outcome.success else 0.0))
