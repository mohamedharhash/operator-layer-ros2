#!/usr/bin/env bash
set -e
source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
source /ws/ros2_ws/install/setup.bash
mkdir -p /ws/data
exec "$@"
