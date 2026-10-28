# What the real (or sim) robot actually did after an APPROVE.
std_msgs/Header header
string action_id
bool executed
bool success
string risk
float64 final_error
float64 duration_s
string robot              # "sim", "so101", ...
