# Operator Layer — rehearse before you execute

**A ROS 2 gate that simulates every proposed robot action N times before the real robot moves, shows the operator the odds, and scores each prediction against what actually happened.**

Learned manipulation policies (ACT, Diffusion Policy, VLAs) are stochastic. A pass/fail test can't tell you whether a policy is safe to run on hardware — but a distribution can. Operator Layer sits between *any* policy and *any* robot and asks one question per action:

> "If we ran this 50 times in sim, how often does it succeed, and how often does it do something we'd regret?"

Then it logs what the robot really did, so the gap between simulation and reality becomes a **tracked metric**, not an anecdote.

```
 policy / planner / VLA                    operator (CLI, console, or auto-policy)
          │  ProposedAction                           ▲
          ▼                                           │ odds, risk, rollouts
 ┌──────────────────┐   RehearsalResult   ┌───────────┴────────┐    Decision     ┌─────────────┐
 │  rehearsal_gate  │ ─────────────────▶ │   gate policy       │ ──────────────▶ │  robot      │
 │  (N sim rollouts)│                    │ auto-approve / ask / │                 │  (SO-101,   │
 └──────────────────┘                    │ auto-reject          │                 │   sim, ...) │
          ▲                              └─────────────────────┘                 └──────┬──────┘
          │                                                                             │ Outcome
          │                              ┌─────────────────────┐                        │
          └──── calibration ─────────────│   episode store     │◀───────────────────────┘
                                         │ predicted vs actual │
                                         └─────────────────────┘
```

## Read the walkthrough first

**[docs/walkthrough.md](docs/walkthrough.md)** ([PDF](docs/walkthrough.pdf)): notes on how I built it and the reasoning behind each part, with the calibration results. About ten minutes.

## What's in the box

| Layer | Package | What it does |
|---|---|---|
| Core (no ROS) | `core/operator_layer_core` | Rehearser, gate policy, episode store, calibration scorer, lightweight SO-101 kinematic sim. Pure Python, fully unit-tested. |
| Messages | `ros2_ws/src/operator_layer_msgs` | `ProposedAction`, `RehearsalResult`, `Decision`, `Outcome` — the interface contract between policy, gate, operator and robot. |
| Nodes | `ros2_ws/src/operator_layer_ros` | `rehearsal_gate_node`, `sim_robot_node`, `outcome_logger_node`, `auto_operator_node` + launch files. |
| Infra | `docker/`, `.github/workflows` | Multi-arch (amd64 + arm64) ROS 2 Humble images; CI runs `pytest` on the core and `colcon build && colcon test` on the ROS packages. |
| Docs | `docs/` | The **walkthrough**, architecture, message contract, and the running **sim-to-real calibration log**. |

## Quickstart (sim only, no hardware)

```bash
git clone https://github.com/<you>/operator-layer-ros2
cd operator-layer-ros2
docker compose -f docker/compose.yml up --build sim
```

That launches the whole loop in simulation: a scripted policy proposes pick-and-place actions, the gate rehearses each one 50×, auto-approves anything above the confidence threshold, the sim robot executes it, and the logger writes predicted-vs-actual rows to `data/episodes.jsonl`.

Watch it:

```bash
ros2 topic echo /operator_layer/rehearsal_result
ros2 topic echo /operator_layer/decision
python -m operator_layer_core.report data/episodes.jsonl   # calibration summary
```

Run the core without ROS at all:

```bash
cd core && pip install -e ".[dev]" && pytest
python -m operator_layer_core.demo    # one full rehearse→decide→execute→score loop in the terminal
```

## Why a gate, and why N rollouts

Three things I believe about physical AI, and that this repo is built around:

1. **Manipulation, not locomotion, is the bottleneck.** Walking is "solved enough"; what fails in the field is the hand near the object. So the unit of gating here is a *manipulation action*, not a trajectory.
2. **Learned policies turn regression testing into statistics.** The right acceptance criterion is "≥ 95% success over N rollouts with no collision class events", not "the test passed." The rehearser produces exactly that distribution.
3. **Sim is only as good as its calibration data.** Every approved action also logs what the real robot did. `docs/sim-to-real.md` tracks how often the sim's odds were right — that number is the real health metric of the system.

This comes from years of verifying many-DOF manipulators that work next to people, where "prove it is safe before it moves" is not optional. Humanoid labs are about to hit the same wall; this is the thin version of that discipline, built for research speed.

## Hardware

The reference arm is a [SO-101](https://github.com/TheRobotStudio/SO-ARM100) driven through LeRobot. The `so101_bridge` is behind a feature flag and only talks to hardware when `OL_ROBOT=so101`. Everything else runs in sim.

## Roadmap

See [ROADMAP.md](ROADMAP.md). Near term: MuJoCo backend for the rehearser, a risk model that's learned from the episode store instead of hand-set, and a Gazebo integration test in CI.

## License

MIT.
