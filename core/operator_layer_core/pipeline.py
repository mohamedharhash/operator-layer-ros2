"""The whole loop, ROS-free: propose -> rehearse -> decide -> execute -> score.

The ROS nodes reproduce exactly this sequence across topics; this class is
what the unit tests exercise, and what `demo.py` runs in a terminal.
"""

from __future__ import annotations

from collections.abc import Callable

from .executor import Executor
from .gate import GatePolicy
from .rehearser import Rehearser
from .store import EpisodeStore
from .types import Decision, EpisodeRecord, ProposedAction, RehearsalResult, Verdict

OperatorFn = Callable[[ProposedAction, RehearsalResult], Decision]


class OperatorLayer:
    def __init__(
        self,
        rehearser: Rehearser,
        gate: GatePolicy,
        executor: Executor,
        store: EpisodeStore,
        operator: OperatorFn | None = None,
    ):
        self.rehearser, self.gate, self.executor, self.store = rehearser, gate, executor, store
        self.operator = operator  # called on ASK_OPERATOR; None => treated as REJECT

    def handle(self, action: ProposedAction) -> EpisodeRecord:
        rehearsal = self.rehearser.rehearse(action)
        decision = self.gate.decide(rehearsal)
        if decision.verdict == Verdict.ASK_OPERATOR:
            if self.operator is not None:
                decision = self.operator(action, rehearsal)
            else:
                decision = Decision(
                    action_id=action.action_id,
                    verdict=Verdict.REJECT,
                    decided_by="auto_policy",
                    reason="ask_operator with no operator attached",
                )
        rec = EpisodeRecord(proposed=action, rehearsal=rehearsal, decision=decision)
        self.store.open(rec)
        if decision.verdict == Verdict.APPROVE:
            outcome = self.executor.execute(action)
            rec = self.store.close(outcome) or rec
        return rec
