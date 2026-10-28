"""Episode store + calibration scoring.

Append-only JSONL: one line per episode. Chosen over a database on purpose —
it survives a crash mid-write, diffs cleanly in git, and `jq`/pandas read it
directly. Swap for Postgres when you have multiple robots writing at once.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .types import EpisodeRecord, Outcome


class EpisodeStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._pending: dict[str, EpisodeRecord] = {}

    # --- lifecycle: a record is pending until its outcome arrives (or it is rejected)
    def open(self, rec: EpisodeRecord) -> None:
        if rec.outcome is not None or rec.decision.verdict.value != "approve":
            self._write(rec)
        else:
            self._pending[rec.proposed.action_id] = rec

    def close(self, outcome: Outcome) -> EpisodeRecord | None:
        rec = self._pending.pop(outcome.action_id, None)
        if rec is None:
            return None
        rec.outcome = outcome
        self._write(rec)
        return rec

    def _write(self, rec: EpisodeRecord) -> None:
        with self.path.open("a") as f:
            f.write(rec.model_dump_json() + "\n")

    def __iter__(self) -> Iterator[EpisodeRecord]:
        if not self.path.exists():
            return iter(())
        with self.path.open() as f:
            return iter([EpisodeRecord.model_validate_json(l) for l in f if l.strip()])


# ------------------------------------------------------------------ calibration
@dataclass
class CalibrationReport:
    n_executed: int
    predicted_success_rate: float  # mean p_success over executed episodes
    actual_success_rate: float  # fraction that really succeeded
    brier_score: float  # mean (p - y)^2; 0 is perfect, 0.25 is coin-flip
    ece: float  # expected calibration error over 10 bins
    bins: list[dict]  # per-bin: range, n, predicted, actual

    def summary(self) -> str:
        gap = self.predicted_success_rate - self.actual_success_rate
        lines = [
            f"executed episodes : {self.n_executed}",
            f"predicted success : {self.predicted_success_rate:.3f}",
            f"actual success    : {self.actual_success_rate:.3f}   (sim-to-real gap {gap:+.3f})",
            f"brier score       : {self.brier_score:.4f}   (0 = perfect, 0.25 = coin flip)",
            f"ECE (10 bins)     : {self.ece:.4f}",
            "",
            "bin        n   predicted  actual",
        ]
        for b in self.bins:
            if b["n"]:
                lines.append(
                    f"{b['lo']:.1f}-{b['hi']:.1f}  {b['n']:4d}   {b['predicted']:.3f}     {b['actual']:.3f}"
                )
        return "\n".join(lines)


def calibrate(records: Iterable[EpisodeRecord], n_bins: int = 10) -> CalibrationReport:
    pairs = [
        (r.rehearsal.p_success, 1.0 if r.outcome.success else 0.0)
        for r in records
        if r.outcome is not None and r.outcome.executed
    ]
    n = len(pairs)
    if n == 0:
        return CalibrationReport(0, math.nan, math.nan, math.nan, math.nan, [])
    pred = sum(p for p, _ in pairs) / n
    act = sum(y for _, y in pairs) / n
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    bins = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        inb = [(p, y) for p, y in pairs if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)]
        if inb:
            bp = sum(p for p, _ in inb) / len(inb)
            ba = sum(y for _, y in inb) / len(inb)
            ece += len(inb) / n * abs(bp - ba)
        else:
            bp = ba = math.nan
        bins.append({"lo": lo, "hi": hi, "n": len(inb), "predicted": bp, "actual": ba})
    return CalibrationReport(n, pred, act, brier, ece, bins)
