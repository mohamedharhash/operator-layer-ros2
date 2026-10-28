"""operator_layer_core — rehearse-before-execute gate for learned robot policies."""

from .executor import SimExecutor
from .gate import GatePolicy, operator_override
from .pipeline import OperatorLayer
from .rehearser import Rehearser
from .sim import KinematicSO101Sim, SO101Params
from .store import EpisodeStore, calibrate
from .types import (
    ActionType,
    Decision,
    EpisodeRecord,
    Outcome,
    ProposedAction,
    RehearsalResult,
    RiskClass,
    RolloutResult,
    Verdict,
)

__all__ = [
    "ActionType",
    "Decision",
    "EpisodeRecord",
    "EpisodeStore",
    "GatePolicy",
    "KinematicSO101Sim",
    "OperatorLayer",
    "Outcome",
    "ProposedAction",
    "RehearsalResult",
    "Rehearser",
    "RiskClass",
    "RolloutResult",
    "SO101Params",
    "SimExecutor",
    "Verdict",
    "calibrate",
    "operator_override",
]
__version__ = "0.2.0"
