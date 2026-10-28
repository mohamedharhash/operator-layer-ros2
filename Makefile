.PHONY: core-test ros-build ros-test image demo lint

core-test:        ## unit tests, no ROS needed
	cd core && pip install -e ".[dev]" -q && pytest -q

demo:             ## terminal demo of the full loop
	cd core && python -m operator_layer_core.demo 60

lint:
	ruff check core && ruff format --check core

ros-build:        ## needs a sourced ROS 2 install
	pip install -e core -q && cd ros2_ws && colcon build --symlink-install

ros-test: ros-build
	cd ros2_ws && . install/setup.sh && colcon test --return-code-on-test-failure && colcon test-result --verbose

image:            ## multi-arch image (needs buildx)
	docker buildx build --platform linux/amd64,linux/arm64 -f docker/Dockerfile -t operator-layer:humble .

sim:              ## full loop in a container
	docker compose -f docker/compose.yml up --build sim
