# Message contract (`operator_layer_msgs`)

All messages carry a `std_msgs/Header` and an `action_id`. The `action_id` is minted by whoever publishes the `ProposedAction` and never changes.

## ProposedAction
| field | type | notes |
|---|---|---|
| action_id | string | 12-char hex by convention |
| source | string | policy identifier, e.g. `act_policy_v3` |
| action_type | string | `move_joints` \| `move_ee` \| `gripper` \| `pick_place` |
| target | float64[] | `move_joints`: 5 joint angles (rad). `move_ee`/`pick_place`: `[x, y, z, yaw]` (m, rad). `gripper`: `[0|1]` |
| context_json | string | JSON. `pick_place` expects `{"object_xyz": [x,y,z]}` |

## RehearsalResult
| field | type | notes |
|---|---|---|
| n_rollouts | uint32 | |
| p_success | float64 | fraction of rollouts that reached the goal |
| p_risk | float64 | fraction with any risk class ≠ none |
| risk_classes / risk_counts | string[] / uint32[] | parallel arrays, histogram |
| mean_final_error | float64 | metres (ee) or radians (joints) |
| sim_backend | string | which sim produced this |
| rollouts | RolloutResult[] | empty unless `keep_rollouts: true` |

Risk classes: `none`, `self_collision`, `workspace_limit`, `object_drop`, `human_proximity`.

## Decision
`verdict` ∈ `approve` | `reject` | `ask_operator`. On `/operator_layer/decision` only `approve`/`reject` ever appear; `ask_operator` is internal to the gate and surfaces as the absence of a decision until the operator (or timeout) resolves it.

## Outcome
Published once per *approved* action. `executed=false` means the robot declined/failed to start (e.g. unsupported action type); `executed=true, success=false` is a real failure and feeds calibration.
