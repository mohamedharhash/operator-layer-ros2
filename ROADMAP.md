# Roadmap

## v0.3 — real arm
- [ ] First SO-101 run: 100 pick-place actions on a 3×3 grid, outcome from overhead camera + lift check
- [ ] Fill in `so101_bridge` LeRobot call-sites against a pinned LeRobot version
- [ ] First real row in `docs/sim-to-real.md`

## v0.4 — calibrated sim
- [ ] Fit sim noise parameters to the episode store (minimise Brier) — `operator_layer_core.calibrate_sim`
- [ ] Per-region gap analysis (workspace heatmap)
- [ ] Rollout-count study: Brier vs N

## v0.5 — physics backend
- [ ] MuJoCo `SimBackend` with the SO-101 MJCF
- [ ] Gazebo integration test in CI (headless)
- [ ] Rehearsal process pool / batched rollouts

## v0.6 — operator console
- [ ] Web console: live rehearsal odds, approve/reject, replay of the N rollouts
- [ ] Export operator corrections as a dataset (LeRobot format) for policy fine-tuning

## Later
- [ ] Learned risk model replacing the hand-set risk classes
- [ ] Multi-robot: one gate per robot, shared episode store (Postgres)
- [ ] C++ gate for sub-millisecond paths (rclcpp), same message contract
