# Sim-to-real calibration log

The single most important number in this project is **how often the rehearser's odds are right**.
Every approved action logs what the robot actually did; this page tracks the gap over time.

## How to read it

| Metric | Meaning | Good |
|---|---|---|
| predicted success | mean `p_success` the sim assigned to executed actions | — |
| actual success | fraction that really succeeded | — |
| **gap** | predicted − actual. Positive = sim is overconfident (dangerous); negative = sim is pessimistic (slow) | \|gap\| < 0.03 |
| Brier score | mean (p − y)²; 0 = perfect, 0.25 = coin flip | < 0.05 |
| ECE | expected calibration error across 10 probability bins | < 0.03 |

Reproduce any row with `python -m operator_layer_core.report <episodes.jsonl>`.

## Log

### 2026-10-27 — v0.2.0, kinematic sim vs "pseudo-real" (sim with noisier params)

Purpose: prove the measurement pipeline end to end before touching hardware. "Reality" here is
`KinematicSO101Sim(joint_noise_std=0.012, grasp_success_base=0.85)` versus the rehearser's
`(0.008, 0.98)`. 200 proposed actions, 109 executed (rest rejected or operator-declined).

```
predicted success : 0.911
actual success    : 0.752   (sim-to-real gap +0.159)
brier score       : 0.2072
ECE (10 bins)     : 0.1589

bin        n   predicted  actual
0.8-0.9    33   0.870     0.636
0.9-1.0    76   0.929     0.803
```

**Reading:** the sim is overconfident by ~16 points, and the overconfidence is *larger* in the
0.8–0.9 bin than in the 0.9–1.0 bin. That pattern — the sim is worst exactly where the gate is
asking the operator — is the argument for calibrating the sim's noise knobs from this data
rather than hand-setting them. Next action: fit `joint_noise_std` and `grasp_success_base`
to minimise Brier on this log, re-run, and confirm the gap shrinks.

### (next) — kinematic sim vs real SO-101

Pending first hardware run. Plan: 100 pick-place actions over a 3×3 grid of object positions,
object pose from a fixed overhead camera, success = object lifted ≥ 3 cm for ≥ 1 s. Expected
gap: unknown — that's the point.

## Open questions this log should eventually answer

- Does the gap depend on where in the workspace the action is? (Hypothesis: yes, worst near the reach limit — lever-arm amplification of joint noise.)
- How many rollouts are enough? Plot Brier vs N; expect diminishing returns past ~30.
- Is a hand-tuned kinematic sim ever good enough, or does the MuJoCo backend pay for itself immediately?
