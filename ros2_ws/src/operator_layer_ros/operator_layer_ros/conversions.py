"""ROS msg <-> core type conversions.

This is the ONLY module that imports both `operator_layer_msgs` and
`operator_layer_core`. Keeping the boundary in one file means the core can be
swapped or versioned without touching node logic, and vice versa.
"""
from __future__ import annotations

import json

from builtin_interfaces.msg import Time
from operator_layer_msgs.msg import Decision, Outcome, ProposedAction, RehearsalResult, RolloutResult
from std_msgs.msg import Header

from operator_layer_core import types as T


def _stamp(sec_float: float) -> Time:
    t = Time()
    t.sec = int(sec_float)
    t.nanosec = int((sec_float - int(sec_float)) * 1e9)
    return t


def _header(stamp: float, frame_id: str = "") -> Header:
    h = Header()
    h.stamp = _stamp(stamp)
    h.frame_id = frame_id
    return h


# ---------------------------------------------------------------- ProposedAction
def proposed_from_msg(m: ProposedAction) -> T.ProposedAction:
    return T.ProposedAction(
        action_id=m.action_id,
        stamp=m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
        source=m.source,
        action_type=T.ActionType(m.action_type),
        target=list(m.target),
        context=json.loads(m.context_json) if m.context_json else {},
    )


def proposed_to_msg(a: T.ProposedAction) -> ProposedAction:
    m = ProposedAction()
    m.header = _header(a.stamp)
    m.action_id = a.action_id
    m.source = a.source
    m.action_type = a.action_type.value
    m.target = [float(x) for x in a.target]
    m.context_json = json.dumps(a.context)
    return m


# ---------------------------------------------------------------- RehearsalResult
def rehearsal_to_msg(r: T.RehearsalResult, stamp: float) -> RehearsalResult:
    m = RehearsalResult()
    m.header = _header(stamp)
    m.action_id = r.action_id
    m.n_rollouts = r.n_rollouts
    m.p_success = r.p_success
    m.p_risk = r.p_risk
    m.risk_classes = list(r.risk_histogram.keys())
    m.risk_counts = [int(v) for v in r.risk_histogram.values()]
    m.mean_final_error = r.mean_final_error
    m.sim_backend = r.sim_backend
    for ro in r.rollouts:
        rm = RolloutResult()
        rm.success, rm.risk, rm.final_error, rm.duration_s = ro.success, ro.risk.value, ro.final_error, ro.duration_s
        m.rollouts.append(rm)
    return m


def rehearsal_from_msg(m: RehearsalResult) -> T.RehearsalResult:
    return T.RehearsalResult(
        action_id=m.action_id, n_rollouts=m.n_rollouts, p_success=m.p_success, p_risk=m.p_risk,
        risk_histogram=dict(zip(m.risk_classes, (int(c) for c in m.risk_counts))),
        mean_final_error=m.mean_final_error, sim_backend=m.sim_backend,
        rollouts=[T.RolloutResult(success=ro.success, risk=T.RiskClass(ro.risk),
                                  final_error=ro.final_error, duration_s=ro.duration_s) for ro in m.rollouts],
    )


# ---------------------------------------------------------------- Decision
def decision_to_msg(d: T.Decision) -> Decision:
    m = Decision()
    m.header = _header(d.stamp)
    m.action_id, m.verdict, m.decided_by, m.reason = d.action_id, d.verdict.value, d.decided_by, d.reason
    return m


def decision_from_msg(m: Decision) -> T.Decision:
    return T.Decision(action_id=m.action_id, verdict=T.Verdict(m.verdict), decided_by=m.decided_by,
                      reason=m.reason, stamp=m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)


# ---------------------------------------------------------------- Outcome
def outcome_to_msg(o: T.Outcome, stamp: float) -> Outcome:
    m = Outcome()
    m.header = _header(stamp)
    m.action_id, m.executed, m.success = o.action_id, o.executed, o.success
    m.risk, m.final_error, m.duration_s, m.robot = o.risk.value, o.final_error, o.duration_s, o.robot
    return m


def outcome_from_msg(m: Outcome) -> T.Outcome:
    return T.Outcome(action_id=m.action_id, executed=m.executed, success=m.success,
                     risk=T.RiskClass(m.risk), final_error=m.final_error, duration_s=m.duration_s, robot=m.robot)
