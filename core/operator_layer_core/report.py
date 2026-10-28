"""`python -m operator_layer_core.report data/episodes.jsonl` -> calibration summary."""

import sys

from .store import EpisodeStore, calibrate

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/episodes.jsonl"
    print(calibrate(EpisodeStore(path)).summary())
