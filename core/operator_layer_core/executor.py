"""Executors: things that actually carry out an approved action and report an Outcome.

`SimExecutor` wraps a SimBackend. In the demo we give it *different* noise
parameters than the rehearser's sim — that mismatch is a stand-in for reality,
and it's what the calibration report measures.

`so101_bridge` (in the ROS package) is the hardware executor; it is only
loaded when OL_ROBOT=so101.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from .sim import SimBackend
from .types import Outcome, ProposedAction


class Executor(Protocol):
    name: str

    def execute(self, action: ProposedAction) -> Outcome: ...


class SimExecutor:
    def __init__(self, backend: SimBackend, name: str = "sim", seed: int | None = None):
        self.backend = backend
        self.name = name
        self.rng = np.random.default_rng(seed)

    def execute(self, action: ProposedAction) -> Outcome:
        r = self.backend.rollout(action, self.rng)
        return Outcome(
            action_id=action.action_id,
            executed=True,
            success=r.success,
            risk=r.risk,
            final_error=r.final_error,
            duration_s=r.duration_s,
            robot=self.name,
        )
