# Contributing

Small, reviewable PRs. Every PR runs the core tests, the ROS build + launch test on Humble and Jazzy, and a multi-arch image build.

## Setup

```bash
pip install pre-commit && pre-commit install
make core-test           # no ROS needed
make ros-test            # with a sourced ROS 2 install
```

## Conventions
- Logic goes in `core/`; ROS nodes only translate and schedule. If you're writing an `if` about robots inside a node, it probably belongs in the core.
- Every message type lives in `operator_layer_msgs`. Changing a message is a minor-version bump and a note in `docs/architecture.md`.
- New safety-relevant behaviour (anything that can change whether the robot moves) needs a test in `core/tests` *and* a line in `config/gate.yaml` if it's tunable.
- Keep `so101_bridge` behind `OL_ROBOT=so101`. Never add a code path that moves hardware without that interlock.
- Calibration runs get a dated section in `docs/sim-to-real.md`, with the command to reproduce them.

## Commit messages
`area: imperative summary` — e.g. `gate: reject on operator timeout`, `sim: fix elbow joint limits`.
