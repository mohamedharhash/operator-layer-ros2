# Architecture

## Principles

1. **Logic in the core, plumbing in ROS.** `operator_layer_core` has no ROS dependency and 100% of the decision logic. ROS nodes translate messages and own timers/QoS. Consequence: unit tests run in under a second with no ROS install; the same core could sit behind gRPC or a plain Python API.
2. **The message contract is the integration point.** Four messages define how a policy team, a sim team, an operator UI and a robot bridge interact. Nobody imports anyone else's code; they publish and subscribe to `operator_layer_msgs`.
3. **Correlate by id, never by time.** Every message carries `action_id`. Joins happen on it. Timing-based correlation is how robotics data pipelines silently rot.
4. **Fail closed.** Unknown sim backend → node refuses to start. Operator timeout → reject. Hardware bridge without `OL_ROBOT=so101` → refuses to start. An exception during execution is an `Outcome` with `success=false`, not a crash.
5. **Every run leaves evidence.** The episode store is append-only JSONL: it survives a crash mid-write, diffs in git, and feeds the calibration report directly.

## Topics

| Topic | Type | Publisher → Subscribers | QoS |
|---|---|---|---|
| `/operator_layer/proposed_action` | `ProposedAction` | policy → gate, robot, logger | reliable, volatile |
| `/operator_layer/rehearsal_result` | `RehearsalResult` | gate → operator, logger | reliable, volatile |
| `/operator_layer/operator_decision` | `Decision` | operator → gate | reliable, volatile |
| `/operator_layer/decision` | `Decision` | gate → robot, logger | reliable, **transient-local** |
| `/operator_layer/outcome` | `Outcome` | robot → logger | reliable, **transient-local** |

Transient-local on decisions and outcomes means a logger or dashboard that starts late still receives the last 50. Rehearsal results are volatile because they can carry per-rollout payloads and are published at the policy rate.

## Per-action sequence

```
policy ──ProposedAction──▶ gate ──(N rollouts)──▶ RehearsalResult ──▶ logger (buffer)
                                                      │
                                   ┌──────────────────┼───────────────────┐
                                 APPROVE          ASK_OPERATOR          REJECT
                                   │                  │                   │
                                   │           operator answers           │
                                   │       (or timeout → REJECT)          │
                                   ▼                  ▼                   ▼
                                Decision ─────────────────────────────▶ logger (opens episode)
                                   │
                                 robot executes ──Outcome──▶ logger (closes episode, writes row)
```

## Swapping parts

| Want to… | Change |
|---|---|
| Use a real learned policy | Publish `ProposedAction` from it. Nothing else changes. |
| Use MuJoCo for rehearsal | Implement `SimBackend.rollout()` and register it in `RehearsalGateNode._make_backend`. |
| Put a human in the loop | Replace `auto_operator` with anything that subscribes to `rehearsal_result` and publishes `operator_decision`. |
| Drive hardware | Run `so101_bridge` instead of `sim_robot` with `OL_ROBOT=so101`. |
| Change the safety contract | Edit `config/gate.yaml`. It is the only file a reviewer needs to read. |

## Scaling notes

- Rehearsal is embarrassingly parallel across rollouts; the kinematic sim does 50 in ~5 ms, MuJoCo will want a process pool or a GPU batch.
- The episode store should move to Postgres (or a bag + index) when multiple robots write concurrently.
- The gate node is stateless apart from the `ASK_OPERATOR` wait-list, so running one per robot is trivial.
