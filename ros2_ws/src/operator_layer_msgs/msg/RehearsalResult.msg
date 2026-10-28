# The distribution over N simulated rollouts. This is what the operator sees.
std_msgs/Header header
string action_id
uint32 n_rollouts
float64 p_success         # fraction of rollouts that succeeded
float64 p_risk            # fraction with any risk event
string[] risk_classes     # parallel arrays: histogram of risk class -> count
uint32[] risk_counts
float64 mean_final_error
string sim_backend
operator_layer_msgs/RolloutResult[] rollouts   # empty unless keep_rollouts is set
