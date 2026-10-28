import numpy as np

from operator_layer_core import (
    ActionType,
    EpisodeStore,
    GatePolicy,
    KinematicSO101Sim,
    OperatorLayer,
    ProposedAction,
    Rehearser,
    RiskClass,
    SimExecutor,
    SO101Params,
    Verdict,
    calibrate,
)
from operator_layer_core.types import Decision, RehearsalResult


def pick(goal, obj=None, **ctx):
    ctx = {"object_xyz": obj or goal, **ctx}
    return ProposedAction(
        source="test", action_type=ActionType.PICK_PLACE, target=list(goal) + [0.0], context=ctx
    )


# ---------------------------------------------------------------- sim
def test_fk_ik_roundtrip():
    sim = KinematicSO101Sim()
    goal = np.array([0.18, 0.05, 0.06])
    q = sim.ik_approx(goal)
    assert q is not None
    assert np.allclose(sim.fk(q), goal, atol=1e-6)


def test_unreachable_is_workspace_limit():
    sim = KinematicSO101Sim()
    r = sim.rollout(pick([0.6, 0.0, 0.05]), np.random.default_rng(0))
    assert not r.success and r.risk == RiskClass.WORKSPACE_LIMIT


def test_human_zone_is_flagged():
    sim = KinematicSO101Sim()
    r = sim.rollout(pick([0.15, -0.22, 0.05]), np.random.default_rng(0))
    assert r.risk == RiskClass.HUMAN_PROXIMITY


# ---------------------------------------------------------------- rehearser
def test_rehearsal_is_a_distribution_and_deterministic_with_seed():
    sim = KinematicSO101Sim()
    a = pick([0.18, 0.05, 0.06])
    r1 = Rehearser(sim, n_rollouts=100, seed=7).rehearse(a)
    r2 = Rehearser(sim, n_rollouts=100, seed=7).rehearse(a)
    assert r1.n_rollouts == 100 and 0.0 <= r1.p_success <= 1.0
    assert r1.p_success == r2.p_success and r1.risk_histogram == r2.risk_histogram


def test_easy_reach_has_high_odds_and_edge_reach_has_lower():
    sim = KinematicSO101Sim()
    easy = Rehearser(sim, 200, seed=1).rehearse(pick([0.18, 0.0, 0.06]))
    edge = Rehearser(sim, 200, seed=1).rehearse(pick([0.295, 0.0, 0.045]))
    assert easy.p_success > 0.9
    assert edge.p_success < easy.p_success


# ---------------------------------------------------------------- gate
def rr(p_success, p_risk=0.0, hist=None, n=50):
    return RehearsalResult(
        action_id="x",
        n_rollouts=n,
        p_success=p_success,
        p_risk=p_risk,
        risk_histogram=hist or {},
        mean_final_error=0.0,
        sim_backend="t",
    )


def test_gate_thresholds():
    g = GatePolicy(approve_threshold=0.95, reject_threshold=0.6, max_risk=0.05)
    assert g.decide(rr(0.98)).verdict == Verdict.APPROVE
    assert g.decide(rr(0.80)).verdict == Verdict.ASK_OPERATOR
    assert g.decide(rr(0.30)).verdict == Verdict.REJECT
    # high success but too much risk is not auto-approved
    assert g.decide(rr(0.98, p_risk=0.1, hist={"object_drop": 5})).verdict == Verdict.ASK_OPERATOR


def test_hard_risk_rejects_even_with_high_success():
    g = GatePolicy()
    d = g.decide(rr(0.99, p_risk=0.02, hist={"human_proximity": 1}))
    assert d.verdict == Verdict.REJECT and "human_proximity" in d.reason


# ---------------------------------------------------------------- store + calibration
def test_store_roundtrip_and_pending_semantics(tmp_path):
    store = EpisodeStore(tmp_path / "e.jsonl")
    sim = KinematicSO101Sim()
    ol = OperatorLayer(
        Rehearser(sim, 30, seed=3),
        GatePolicy(approve_threshold=0.85, max_risk=0.2),
        SimExecutor(sim, seed=4),
        store,
    )
    recs = [ol.handle(pick([0.18, 0.0, 0.06])) for _ in range(5)]
    assert all(r.decision.verdict == Verdict.APPROVE for r in recs)
    assert all(r.outcome is not None and r.outcome.executed for r in recs)
    assert len(list(store)) == 5
    assert not store._pending


def test_rejected_actions_are_logged_without_outcome(tmp_path):
    store = EpisodeStore(tmp_path / "e.jsonl")
    sim = KinematicSO101Sim()
    ol = OperatorLayer(Rehearser(sim, 30, seed=3), GatePolicy(), SimExecutor(sim, seed=4), store)
    rec = ol.handle(pick([0.15, -0.22, 0.05]))  # human zone
    assert rec.decision.verdict == Verdict.REJECT and rec.outcome is None
    assert len(list(store)) == 1


def test_ask_operator_routes_to_operator(tmp_path):
    store = EpisodeStore(tmp_path / "e.jsonl")
    sim = KinematicSO101Sim()
    seen = []

    def operator(a, r):
        seen.append(r.p_success)
        return Decision(
            action_id=a.action_id, verdict=Verdict.APPROVE, decided_by="mohamed", reason="ok"
        )

    ol = OperatorLayer(
        Rehearser(sim, 50, seed=1),
        GatePolicy(approve_threshold=1.01),
        SimExecutor(sim, seed=4),
        store,
        operator=operator,
    )
    rec = ol.handle(pick([0.18, 0.0, 0.06]))
    assert seen and rec.decision.decided_by == "mohamed" and rec.outcome is not None


def test_calibration_detects_sim_to_real_gap(tmp_path):
    good = KinematicSO101Sim(SO101Params())
    bad = KinematicSO101Sim(SO101Params(grasp_success_base=0.5))
    store = EpisodeStore(tmp_path / "e.jsonl")
    ol = OperatorLayer(
        Rehearser(good, 50, seed=1),
        GatePolicy(approve_threshold=0.85, max_risk=0.2),
        SimExecutor(bad, seed=2),
        store,
    )
    for _ in range(40):
        ol.handle(pick([0.18, 0.0, 0.06]))
    rep = calibrate(store)
    assert rep.n_executed >= 30  # a few may land in the grey zone and be rejected
    assert rep.predicted_success_rate - rep.actual_success_rate > 0.2  # sim is overconfident
    assert rep.brier_score > 0.1


def test_calibration_empty():
    rep = calibrate([])
    assert rep.n_executed == 0
