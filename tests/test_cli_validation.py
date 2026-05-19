"""Regression tests for CLI argument validation (Issue #6)."""

import subprocess
import sys


def test_cli_rejects_invalid_output_mode():
    """Passing an unsupported --output-mode must fail with exit code 2."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "--output-mode", "xml", "status"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"


def test_cli_accepts_valid_output_mode():
    """Passing a supported --output-mode must succeed."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "--output-mode", "json", "status"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_default_output_mode():
    """Omitting --output-mode must succeed with default."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
