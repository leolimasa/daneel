"""Tests for the daneel module."""

import json
import tempfile
import unittest.mock
from pathlib import Path

import pytest
import yaml

from daneel import Output, checkbox_progress, claude_code, update_yml, validate


class TestOutput:
    """Tests for the Output dataclass."""

    def test_output_creation(self):
        """Test Output dataclass creation with valid inputs."""
        output = Output(stdout="hello", stderr="")
        assert output.stdout == "hello"
        assert output.stderr == ""
        assert output.structured is None

    def test_output_with_structured(self):
        """Test Output creation with structured data."""
        structured_data = {"key": "value"}
        output = Output(stdout="", stderr="", structured=structured_data)
        assert output.structured == structured_data

    def test_output_validation_stdout_type(self):
        """Test that stdout must be a string."""
        with pytest.raises(TypeError, match="stdout must be a string"):
            Output(stdout=123, stderr="")

    def test_output_validation_stderr_type(self):
        """Test that stderr must be a string."""
        with pytest.raises(TypeError, match="stderr must be a string"):
            Output(stdout="", stderr=123)

    def test_output_validation_structured_type(self):
        """Test that structured must be a dict or None."""
        with pytest.raises(TypeError, match="structured must be a dictionary or None"):
            Output(stdout="", stderr="", structured="not a dict")


class TestClaudeCode:
    """Tests for the claude_code function."""

    @unittest.mock.patch('daneel.subprocess.run')
    def test_claude_code_success(self, mock_run):
        """Test successful claude_code execution."""
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout="Hello world",
            stderr=""
        )
        
        result = claude_code("test prompt")
        
        assert result.stdout == "Hello world"
        assert result.stderr == ""
        assert result.structured is None
        mock_run.assert_called_once_with(
            ["claude", "test prompt"],
            capture_output=True,
            text=True,
            timeout=120
        )

    @unittest.mock.patch('daneel.subprocess.run')
    def test_claude_code_structured(self, mock_run):
        """Test claude_code with structured output."""
        json_output = '{"result": "success", "data": [1, 2, 3]}'
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout=json_output,
            stderr=""
        )
        
        result = claude_code("test prompt", structured=True)
        
        assert result.structured == {"result": "success", "data": [1, 2, 3]}
        # Check that prompt was modified to request JSON
        args = mock_run.call_args[0][0]
        assert "Please respond with valid JSON only." in args[1]

    @unittest.mock.patch('daneel.subprocess.run')
    def test_claude_code_invalid_json(self, mock_run):
        """Test claude_code with invalid JSON output."""
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout="invalid json {",
            stderr=""
        )
        
        with pytest.raises(Exception, match="Failed to parse JSON output"):
            claude_code("test prompt", structured=True)

    @unittest.mock.patch('daneel.subprocess.run')
    def test_claude_code_retry_success(self, mock_run):
        """Test claude_code retry mechanism."""
        # First call fails, second succeeds
        mock_run.side_effect = [
            unittest.mock.Mock(returncode=1, stdout="", stderr="error"),
            unittest.mock.Mock(returncode=0, stdout="success", stderr="")
        ]
        
        with unittest.mock.patch('daneel.time.sleep'):
            result = claude_code("test prompt", retries=1)
        
        assert result.stdout == "success"
        assert mock_run.call_count == 2

    @unittest.mock.patch('daneel.subprocess.run')
    def test_claude_code_timeout(self, mock_run):
        """Test claude_code timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)
        
        with pytest.raises(Exception, match="Command timed out"):
            claude_code("test prompt", retries=0)

    @unittest.mock.patch('daneel.subprocess.run')
    def test_claude_code_not_found(self, mock_run):
        """Test claude_code when claude command is not found."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(Exception, match="Claude command not found"):
            claude_code("test prompt")


class TestValidate:
    """Tests for the validate function."""

    @unittest.mock.patch('daneel.subprocess.run')
    def test_validate_success(self, mock_run):
        """Test successful validate execution."""
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout="success",
            stderr=""
        )
        
        def dummy_fail_fn(output):
            return Output("fixed", "")
        
        result = validate("echo success", dummy_fail_fn)
        
        assert result.stdout == "success"
        mock_run.assert_called_once()

    @unittest.mock.patch('daneel.subprocess.run')
    def test_validate_with_failure_function(self, mock_run):
        """Test validate with failure function."""
        mock_run.side_effect = [
            unittest.mock.Mock(returncode=1, stdout="", stderr="error"),
            unittest.mock.Mock(returncode=0, stdout="fixed", stderr="")
        ]
        
        fail_fn_called = False
        def fail_fn(output):
            nonlocal fail_fn_called
            fail_fn_called = True
            assert output.stderr == "error"
            return Output("repair attempted", "")
        
        with unittest.mock.patch('daneel.time.sleep'):
            result = validate("test command", fail_fn, retries=1)
        
        assert result.stdout == "fixed"
        assert fail_fn_called
        assert mock_run.call_count == 2

    @unittest.mock.patch('daneel.subprocess.run')
    def test_validate_all_retries_fail(self, mock_run):
        """Test validate when all retries fail."""
        mock_run.return_value = unittest.mock.Mock(
            returncode=1,
            stdout="",
            stderr="persistent error"
        )
        
        def dummy_fail_fn(output):
            return Output("tried to fix", "")
        
        with unittest.mock.patch('daneel.time.sleep'):
            with pytest.raises(Exception, match="Command failed after"):
                validate("failing command", dummy_fail_fn, retries=1)


class TestUpdateYml:
    """Tests for the update_yml function."""

    def test_update_yml_simple_field(self):
        """Test updating a simple YAML field."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.safe_dump({"name": "old_value", "version": "1.0"}, f)
            temp_path = f.name
        
        try:
            update_yml(temp_path, "name", "new_value")
            
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data["name"] == "new_value"
            assert data["version"] == "1.0"
        finally:
            Path(temp_path).unlink()

    def test_update_yml_nested_field(self):
        """Test updating a nested YAML field."""
        initial_data = {
            "app": {
                "config": {
                    "debug": False,
                    "port": 8080
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.safe_dump(initial_data, f)
            temp_path = f.name
        
        try:
            update_yml(temp_path, "app.config.debug", True)
            
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data["app"]["config"]["debug"] is True
            assert data["app"]["config"]["port"] == 8080
        finally:
            Path(temp_path).unlink()

    def test_update_yml_array_index(self):
        """Test updating an array element in YAML."""
        initial_data = {
            "items": ["first", "second", "third"]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.safe_dump(initial_data, f)
            temp_path = f.name
        
        try:
            update_yml(temp_path, "items[1]", "updated_second")
            
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data["items"] == ["first", "updated_second", "third"]
        finally:
            Path(temp_path).unlink()

    def test_update_yml_create_nested_structure(self):
        """Test creating new nested structure in YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.safe_dump({"existing": "field"}, f)
            temp_path = f.name
        
        try:
            update_yml(temp_path, "new.nested.field", "value")
            
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data["new"]["nested"]["field"] == "value"
            assert data["existing"] == "field"
        finally:
            Path(temp_path).unlink()

    def test_update_yml_file_not_found(self):
        """Test update_yml with non-existent file."""
        with pytest.raises(FileNotFoundError, match="YAML file not found"):
            update_yml("/nonexistent/file.yml", "field", "value")

    def test_update_yml_invalid_field_query(self):
        """Test update_yml with invalid field query."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.safe_dump({"test": "value"}, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid field query"):
                update_yml(temp_path, "items[invalid]", "value")
        finally:
            Path(temp_path).unlink()


class TestCheckboxProgress:
    """Tests for the checkbox_progress function."""

    def test_checkbox_progress_mixed(self):
        """Test checkbox progress calculation with mixed checkboxes."""
        content = """
# TODO List

- [x] Completed task 1
- [ ] Incomplete task 1
- [x] Completed task 2
- [ ] Incomplete task 2
- [x] Completed task 3

Some other content
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            progress = checkbox_progress(temp_path)
            assert progress == 0.6  # 3 out of 5 completed
        finally:
            Path(temp_path).unlink()

    def test_checkbox_progress_all_completed(self):
        """Test checkbox progress with all tasks completed."""
        content = """
- [x] Task 1
- [x] Task 2
- [x] Task 3
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            progress = checkbox_progress(temp_path)
            assert progress == 1.0
        finally:
            Path(temp_path).unlink()

    def test_checkbox_progress_none_completed(self):
        """Test checkbox progress with no tasks completed."""
        content = """
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            progress = checkbox_progress(temp_path)
            assert progress == 0.0
        finally:
            Path(temp_path).unlink()

    def test_checkbox_progress_no_checkboxes(self):
        """Test checkbox progress with no checkboxes in file."""
        content = """
# Regular markdown

Some content without checkboxes.

* Regular bullet
* Another bullet
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            progress = checkbox_progress(temp_path)
            assert progress == 0.0
        finally:
            Path(temp_path).unlink()

    def test_checkbox_progress_various_formats(self):
        """Test checkbox progress with various checkbox formats."""
        content = """
- [x] Standard completed
- [ ] Standard incomplete  
* [x] Asterisk completed
* [ ] Asterisk incomplete
  - [X] Indented and uppercase X
  - [ ] Indented incomplete
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            progress = checkbox_progress(temp_path)
            assert progress == 0.5  # 3 out of 6 completed
        finally:
            Path(temp_path).unlink()

    def test_checkbox_progress_file_not_found(self):
        """Test checkbox_progress with non-existent file."""
        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            checkbox_progress("/nonexistent/file.md")


# Fix import issue for subprocess.TimeoutExpired
import subprocess