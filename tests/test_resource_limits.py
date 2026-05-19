"""Tests for resource limit validation."""

import pytest
from src.agent.sandbox import ResourceLimits, _validate_resource_limits


class TestResourceLimitsValidation:
    """Regression tests for Issue #5 — Config validation."""

    def test_default_limits_are_valid(self):
        """Default constructor values should pass validation."""
        limits = ResourceLimits()
        assert limits.cpu_time == 60
        assert limits.memory_mb == 512
        assert limits.disk_mb == 100

    def test_custom_limits_are_valid(self):
        """Explicit positive values should pass."""
        limits = ResourceLimits(cpu_time=120, memory_mb=1024, disk_mb=500)
        assert limits.cpu_time == 120

    @pytest.mark.parametrize("field,value", [
        ("cpu_time", 0),
        ("cpu_time", -1),
        ("memory_mb", 0),
        ("memory_mb", -512),
        ("disk_mb", 0),
        ("disk_mb", -100),
    ])
    def test_zero_or_negative_raises(self, field, value):
        """Zero or negative values must raise ValueError."""
        kwargs = {"cpu_time": 60, "memory_mb": 512, "disk_mb": 100}
        kwargs[field] = value
        with pytest.raises(ValueError):
            ResourceLimits(**kwargs)

    def test_validate_helper_rejects_all_negative(self):
        """Direct validation helper must reject negative values."""
        with pytest.raises(ValueError):
            _validate_resource_limits(-1, 512, 100)
        with pytest.raises(ValueError):
            _validate_resource_limits(60, -1, 100)
        with pytest.raises(ValueError):
            _validate_resource_limits(60, 512, -1)
