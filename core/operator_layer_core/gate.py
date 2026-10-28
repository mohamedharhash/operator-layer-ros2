"""Gate policy: turn a rehearsal distribution into APPROVE / REJECT / ASK_OPERATOR.

The thresholds are the operator's safety contract. They are deliberately
simple and explicit — a reviewer should be able to read this file and know
exactly when the robot is allowed to move without a human in the loop.

Rules (evaluated in order):
  1. Any rollout hitting a *hard* risk class (human proximity by default) -> REJECT.
  2. p_success >= approve_threshold and p_risk <= max_risk        -> APPROVE.
  3. p_success <  reject_threshold                                 -> REJECT.
  4. otherwise                                                     -> ASK_OPERATOR.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import Decision, RehearsalResult, RiskClass, Verdict


@dataclass
class GatePolicy:
    approve_threshold: float = 0.95
    reject_threshold: float = 0.60
    max_risk: float = 0.05
    hard_risks: set[RiskClass] = field(default_factory=lambda: {RiskClass.HUMAN_PROXIMITY})
    decided_by: str = "auto_policy"

    def decide(self, r: RehearsalResult) -> Decision:
        for risk in self.hard_risks:
            if r.risk_histogram.get(risk.value, 0) > 0:
                return Decision(
                    action_id=r.action_id,
                    verdict=Verdict.REJECT,
                    decided_by=self.decided_by,
                    reason=f"hard risk {risk.value} seen in {r.risk_histogram[risk.value]}/{r.n_rollouts} rollouts",
                )
        if r.p_success >= self.approve_threshold and r.p_risk <= self.max_risk:
            return Decision(
                action_id=r.action_id,
                verdict=Verdict.APPROVE,
                decided_by=self.decided_by,
                reason=f"p_success={r.p_success:.2f} >= {self.approve_threshold}, p_risk={r.p_risk:.2f}",
            )
        if r.p_success < self.reject_threshold:
            return Decision(
                action_id=r.action_id,
                verdict=Verdict.REJECT,
                decided_by=self.decided_by,
                reason=f"p_success={r.p_success:.2f} < {self.reject_threshold}",
            )
        return Decision(
            action_id=r.action_id,
            verdict=Verdict.ASK_OPERATOR,
            decided_by=self.decided_by,
            reason=f"p_success={r.p_success:.2f} in grey zone; p_risk={r.p_risk:.2f}",
        )


def operator_override(
    r: RehearsalResult, approve: bool, operator_id: str, note: str = ""
) -> Decision:
    """A human answering an ASK_OPERATOR."""
    return Decision(
        action_id=r.action_id,
        verdict=Verdict.APPROVE if approve else Verdict.REJECT,
        decided_by=operator_id,
        reason=note or ("operator approved" if approve else "operator rejected"),
    )
