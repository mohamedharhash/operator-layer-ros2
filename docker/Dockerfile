# Operator Layer — ROS 2 Humble, multi-arch (linux/amd64 + linux/arm64).
#
# The ros:humble base is published for both architectures, so the same
# Dockerfile builds for an x86 workstation and a Jetson/ARM robot computer:
#
#   docker buildx build --platform linux/amd64,linux/arm64 -f docker/Dockerfile -t operator-layer:humble .
#
# Two stages:
#   builder  — installs deps, builds the colcon workspace
#   runtime  — copies only the install/ tree; no build tools, smaller image
ARG ROS_DISTRO=humble

# ---------------------------------------------------------------------- builder
FROM ros:${ROS_DISTRO}-ros-base AS builder
ARG ROS_DISTRO
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip python3-colcon-common-extensions python3-rosdep \
      ros-${ROS_DISTRO}-launch-testing ros-${ROS_DISTRO}-launch-testing-ros \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws
# Core first (changes less often than node code -> better layer caching)
COPY core/ /ws/core/
RUN pip3 install --no-cache-dir /ws/core

COPY ros2_ws/src/ /ws/ros2_ws/src/
# ldconfig: under QEMU (arm64 cross-build) the shared-library cache is stale and
# CMake can't resolve ROS libs that are present on disk.
RUN ldconfig \
    && . /opt/ros/${ROS_DISTRO}/setup.sh \
    && cd /ws/ros2_ws \
    && colcon build --symlink-install --event-handlers console_direct+ \
         --cmake-args -DCMAKE_BUILD_TYPE=Release

# ---------------------------------------------------------------------- runtime
FROM ros:${ROS_DISTRO}-ros-base AS runtime
ARG ROS_DISTRO
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3*/dist-packages /usr/local/lib/python3/dist-packages
COPY --from=builder /ws/core /ws/core
RUN pip3 install --no-cache-dir /ws/core
COPY --from=builder /ws/ros2_ws/install /ws/ros2_ws/install
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /ws
# Fast-RTPS default; set RMW_IMPLEMENTATION=rmw_cyclonedds_cpp to switch.
ENV ROS_DOMAIN_ID=0 OL_ROBOT=sim
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "operator_layer_ros", "sim.launch.py"]
