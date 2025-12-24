"""Tests for build system integration."""

import subprocess
import sys
from pathlib import Path


def test_nix_build_success():
    """Test that nix build completes successfully."""
    project_root = Path(__file__).parent.parent
    
    try:
        result = subprocess.run(
            ["nix", "build", "--print-build-logs"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for build
        )
        assert result.returncode == 0, f"Nix build failed: {result.stderr}"
        
        # Check that result symlink exists
        result_path = project_root / "result"
        assert result_path.exists(), "Build result symlink not found"
        
        # Check that daneel binary exists
        daneel_bin = result_path / "bin" / "daneel"
        assert daneel_bin.exists(), "Daneel binary not found"
        assert daneel_bin.is_file(), "Daneel binary is not a file"
        
    except subprocess.TimeoutExpired:
        pytest.fail("Nix build timed out")
    except FileNotFoundError:
        pytest.skip("Nix not available in test environment")


def test_daneel_module_importable():
    """Test that daneel module can be imported after build."""
    project_root = Path(__file__).parent.parent
    result_path = project_root / "result"
    
    if not result_path.exists():
        pytest.skip("Build result not available, run nix build first")
    
    lib_path = result_path / "lib" / "python"
    
    # Test importing the module
    test_script = f'''
import sys
sys.path.insert(0, "{lib_path}")
import daneel

# Test that all functions are available
from daneel import Output, claude_code, validate, update_yml, checkbox_progress

# Test Output creation
output = Output("test", "")
assert output.stdout == "test"

print("All imports and basic functionality working")
'''
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"Import test failed: {result.stderr}"
        assert "All imports and basic functionality working" in result.stdout
        
    except subprocess.TimeoutExpired:
        pytest.fail("Import test timed out")


def test_package_consumable_by_other_flakes():
    """Test that the flake can be used as a dependency."""
    project_root = Path(__file__).parent.parent
    
    # Create a temporary test flake that uses our daneel package
    test_flake_content = '''
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    daneel.url = "path:''' + str(project_root) + '''";
  };

  outputs = { self, nixpkgs, flake-utils, daneel }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        packages.test = pkgs.writeShellScript "test-daneel" \'\'
          echo "Testing daneel package availability"
          ${daneel.packages.${system}.default}/bin/daneel
        \'\';
      });
}
'''
    
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        flake_file = temp_path / "flake.nix"
        
        with open(flake_file, 'w') as f:
            f.write(test_flake_content)
        
        try:
            # Test that the flake can be evaluated
            result = subprocess.run(
                ["nix", "flake", "show", "--json"],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            assert result.returncode == 0, f"Test flake evaluation failed: {result.stderr}"
            
            import json
            flake_info = json.loads(result.stdout)
            assert "packages" in flake_info
            
        except subprocess.TimeoutExpired:
            pytest.fail("Flake evaluation timed out")
        except FileNotFoundError:
            pytest.skip("Nix not available in test environment")


def test_development_shell_available():
    """Test that development shell provides expected tools."""
    project_root = Path(__file__).parent.parent
    
    try:
        # Test that dev shell has expected tools
        result = subprocess.run(
            ["nix", "develop", "--command", "which", "python"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, "Python not available in dev shell"
        
        result = subprocess.run(
            ["nix", "develop", "--command", "which", "pytest"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, "Pytest not available in dev shell"
        
        result = subprocess.run(
            ["nix", "develop", "--command", "which", "mypy"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, "Mypy not available in dev shell"
        
        result = subprocess.run(
            ["nix", "develop", "--command", "which", "uv"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, "UV not available in dev shell"
        
    except subprocess.TimeoutExpired:
        pytest.fail("Development shell test timed out")
    except FileNotFoundError:
        pytest.skip("Nix not available in test environment")


# Import pytest for proper test discovery
import pytest