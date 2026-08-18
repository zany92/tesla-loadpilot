"""Pytest fixtures for the pure control-policy tests (no HA harness).

control.py has zero Home Assistant imports, but importing it as
``custom_components.loadpilot.control`` would first execute the package
__init__.py, which DOES import Home Assistant. It is therefore loaded
straight from its file path and registered as the standalone module
``loadpilot_control`` (the tests ``import loadpilot_control``).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_CONTROL_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "loadpilot"
    / "control.py"
)

_spec = importlib.util.spec_from_file_location(
    "loadpilot_control", _CONTROL_PATH
)
_module = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
sys.modules["loadpilot_control"] = _module
_spec.loader.exec_module(_module)


@pytest.fixture
def params_tri():
    """Three-phase pilot calibration: bias max 16 A, L = 21 A."""
    return _module.ControlParams(bias_max_a=16.0, max_conductor_a=21.0)


@pytest.fixture
def params_mono():
    """Single-phase (theoretical): bias max 32 A, L = 32 A."""
    return _module.ControlParams(bias_max_a=32.0, max_conductor_a=32.0)
