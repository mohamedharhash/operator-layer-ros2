"""Shim for toolchains too old to read PEP 621 metadata from pyproject.toml
(Ubuntu 22.04 ships pip 22 / setuptools 59, which build an 'UNKNOWN-0.0.0'
wheel from this project otherwise). Modern pip ignores this file's values and
reads pyproject.toml directly; the two must agree."""
from setuptools import find_packages, setup

setup(
    name="operator-layer-core",
    version="0.2.0",
    packages=find_packages(include=["operator_layer_core*"]),
    install_requires=["numpy>=1.24", "pydantic>=2.0"],
    python_requires=">=3.10",
)
