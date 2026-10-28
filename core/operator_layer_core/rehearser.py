"""Rehearser: run a proposed action N times in sim and summarise the distribution."""

from __future__ import annotations

from collections import Counter

import numpy as np

from .sim import SimBackend
from .types import ProposedAction, RehearsalResult


class Rehearser:
    def __init__(
        self,
        backend: SimBackend,
        n_rollouts: int = 50,
        seed: int | None = None,
        keep_rollouts: bool = False,
    ):
        self.backend = backend
        self.n = n_rollouts
        self.rng = np.random.default_rng(seed)
        self.keep_rollouts = keep_rollouts

    def rehearse(self, action: ProposedAction) -> RehearsalResult:
        rollouts = [self.backend.rollout(action, self.rng) for _ in range(self.n)]
        n_ok = sum(r.success for r in rollouts)
        n_risk = sum(r.risk.value != "none" for r in rollouts)
        hist = Counter(r.risk.value for r in rollouts if r.risk.value != "none")
        mean_err = float(np.mean([r.final_error for r in rollouts])) if rollouts else 0.0
        return RehearsalResult(
            action_id=action.action_id,
            n_rollouts=self.n,
            p_success=n_ok / self.n,
            p_risk=n_risk / self.n,
            risk_histogram=dict(hist),
            mean_final_error=mean_err,
            sim_backend=self.backend.name,
            rollouts=rollouts if self.keep_rollouts else [],
        )
