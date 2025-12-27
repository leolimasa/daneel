"""Tests for environment setup and configuration."""

import subprocess
import sys
from pathlib import Path


def test_python_version():
    """Test that Python version is 3.11+"""
    assert sys.version_info >= (3, 11), f"Python version {sys.version} is not 3.11+"


def test_required_modules_available():
    """Test that required modules can be imported."""
    try:
        import yaml
        import pytest
        import pexpect
    except ImportError as e:
        pytest.fail(f"Required module not available: {e}")


def test_project_structure():
    """Test that project has correct structure."""
    project_root = Path(__file__).parent.parent
    
    assert (project_root / "flake.nix").exists(), "flake.nix not found"
    assert (project_root / "pyproject.toml").exists(), "pyproject.toml not found"


def test_flake_builds():
    """Test that nix flake can be evaluated."""
    project_root = Path(__file__).parent.parent
    
    try:
        result = subprocess.run(
            ["nix", "flake", "show", "--json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"Flake evaluation failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        pytest.fail("Flake evaluation timed out")
    except FileNotFoundError:
        pytest.skip("Nix not available in test environment")