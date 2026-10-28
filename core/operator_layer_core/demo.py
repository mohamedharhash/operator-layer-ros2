"""Terminal demo: `python -m operator_layer_core.demo [n_actions]`.

A scripted policy proposes pick-and-place actions across the workspace
(some easy, some near the reach limit, one inside the human zone). The gate
rehearses each one, decides, the "real" robot (a sim with different noise)
executes approved ones, and a calibration report is printed at the end.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

from .executor import SimExecutor
from .gate import GatePolicy
from .pipeline import OperatorLayer
from .rehearser import Rehearser
from .sim import KinematicSO101Sim, SO101Params
from .store import EpisodeStore, calibrate
from .types import ActionType, Decision, ProposedAction, Verdict


def scripted_policy(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    for i in range(n):
        if i % 10 == 7:  # occasionally propose something inside the human zone
            goal = [0.15, -0.22, 0.05]
        else:
            r = rng.uniform(0.12, 0.30)  # includes the hard outer band
            th = rng.uniform(-1.2, 1.2)
            goal = [r * np.cos(th), r * np.sin(th), rng.uniform(0.02, 0.12)]
        obj = list(np.asarray(goal) + rng.normal(0, 0.004, 3))  # perception error on object pose
        yield ProposedAction(
            source="scripted_v1",
            action_type=ActionType.PICK_PLACE,
            target=goal + [0.0],
            context={"object_xyz": obj},
        )


def stand_in_operator(action, rehearsal):
    """Plays the human for the demo: approves grey-zone actions with p_success >= 0.85."""
    ok = rehearsal.p_success >= 0.85
    return Decision(
        action_id=action.action_id,
        verdict=Verdict.APPROVE if ok else Verdict.REJECT,
        decided_by="demo_operator",
        reason=f"operator {'approved' if ok else 'declined'} at p={rehearsal.p_success:.2f}",
    )


def main(n_actions: int = 60) -> None:
    rehearse_sim = KinematicSO101Sim(SO101Params())
    # "reality" is a little worse than the sim thinks: more joint noise, weaker grasp
    real_sim = KinematicSO101Sim(SO101Params(joint_noise_std=0.012, grasp_success_base=0.85))

    with tempfile.TemporaryDirectory() as d:
        store = EpisodeStore(Path(d) / "episodes.jsonl")
        ol = OperatorLayer(
            Rehearser(rehearse_sim, n_rollouts=50, seed=1),
            GatePolicy(),
            SimExecutor(real_sim, name="pseudo_real", seed=2),
            store,
            operator=stand_in_operator,
        )
        print(f"{'id':12} {'p_succ':>6} {'p_risk':>6}  {'verdict':13} {'real':6}  reason")
        for a in scripted_policy(n_actions):
            rec = ol.handle(a)
            real = (
                "-"
                if rec.outcome is None
                else ("ok" if rec.outcome.success else rec.outcome.risk.value)
            )
            print(
                f"{a.action_id:12} {rec.rehearsal.p_success:6.2f} {rec.rehearsal.p_risk:6.2f}  "
                f"{rec.decision.verdict.value:13} {real:6}  {rec.decision.reason}"
            )
        print("\n== calibration (sim vs pseudo-real) ==")
        print(calibrate(store).summary())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
