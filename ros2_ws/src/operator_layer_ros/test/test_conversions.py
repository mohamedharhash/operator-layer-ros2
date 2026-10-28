"""Round-trip tests for the ROS<->core boundary. Runs under colcon test."""
import json

import pytest

try:
    from operator_layer_msgs.msg import ProposedAction  # noqa: F401
except ImportError:  # pragma: no cover
    pytest.skip("operator_layer_msgs not built; run under colcon", allow_module_level=True)

from operator_layer_core import types as T
from operator_layer_ros import conversions as C


def test_proposed_roundtrip():
    a = T.ProposedAction(source="s", action_type=T.ActionType.PICK_PLACE, target=[0.1, 0.2, 0.3, 0.0],
                         context={"object_xyz": [0.1, 0.2, 0.3]})
    b = C.proposed_from_msg(C.proposed_to_msg(a))
    assert b.action_id == a.action_id and b.target == a.target and b.context == a.context
    assert abs(b.stamp - a.stamp) < 1e-6


def test_rehearsal_roundtrip_histogram():
    r = T.RehearsalResult(action_id="x", n_rollouts=50, p_success=0.9, p_risk=0.1,
                          risk_histogram={"object_drop": 4, "workspace_limit": 1},
                          mean_final_error=0.01, sim_backend="t",
                          rollouts=[T.RolloutResult(success=False, risk=T.RiskClass.OBJECT_DROP)])
    m = C.rehearsal_to_msg(r, 1.0)
    assert dict(zip(m.risk_classes, m.risk_counts)) == {"object_drop": 4, "workspace_limit": 1}
    back = C.rehearsal_from_msg(m)
    assert back.risk_histogram == r.risk_histogram and back.rollouts[0].risk == T.RiskClass.OBJECT_DROP


def test_decision_and_outcome_roundtrip():
    d = T.Decision(action_id="x", verdict=T.Verdict.ASK_OPERATOR, decided_by="auto_policy", reason="grey")
    assert C.decision_from_msg(C.decision_to_msg(d)).verdict == T.Verdict.ASK_OPERATOR
    o = T.Outcome(action_id="x", executed=True, success=False, risk=T.RiskClass.OBJECT_DROP, robot="so101")
    b = C.outcome_from_msg(C.outcome_to_msg(o, 2.0))
    assert b.risk == T.RiskClass.OBJECT_DROP and b.robot == "so101" and b.executed


def test_context_json_is_valid_json():
    a = T.ProposedAction(source="s", action_type=T.ActionType.MOVE_EE, target=[0.1, 0.0, 0.1, 0.0],
                         context={"nested": {"k": [1, 2]}})
    assert json.loads(C.proposed_to_msg(a).context_json) == a.context
