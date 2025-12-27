"""Tests for the daneel module."""

import json
import subprocess
import tempfile
import unittest.mock
from pathlib import Path

import pytest
import yaml

from daneel import Output, checkbox_progress, claude_code, update_yml, validate, main


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

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_claude_code_success(self, mock_stderr, mock_stdout, mock_select, mock_popen, mock_find_git_root):
        """Test successful claude_code execution."""
        mock_find_git_root.return_value = "/test/repo"
        
        # Mock the process
        mock_process = unittest.mock.Mock()
        mock_process.poll.side_effect = [None, None, 0]  # Running, then finished
        mock_process.returncode = 0
        mock_process.stdout.readline.side_effect = ["Hello world\n", ""]
        mock_process.stderr.readline.side_effect = ["", ""]
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        # Mock select to return stdout ready once, then nothing
        mock_select.side_effect = [
            ([mock_process.stdout], [], []),  # First call: stdout ready
            ([], [], []),  # Second call: nothing ready
            ([], [], [])   # Third call: nothing ready (process finished)
        ]
        
        result = claude_code("test prompt")
        
        assert result.stdout == "Hello world\n"
        assert result.stderr == ""
        assert result.structured is None
        mock_popen.assert_called_once_with(
            ["claude", "-p", "--verbose", "test prompt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/test/repo",
            bufsize=1,
            universal_newlines=True
        )

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_claude_code_structured(self, mock_stderr, mock_stdout, mock_select, mock_popen, mock_find_git_root):
        """Test claude_code with structured output."""
        mock_find_git_root.return_value = "/test/repo"
        json_output = '{"result": "success", "data": [1, 2, 3]}'
        
        # Mock the process
        mock_process = unittest.mock.Mock()
        mock_process.poll.side_effect = [None, 0]  # Running, then finished
        mock_process.returncode = 0
        mock_process.stdout.readline.side_effect = [json_output, ""]
        mock_process.stderr.readline.side_effect = ["", ""]
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        # Mock select to return stdout ready once
        mock_select.side_effect = [
            ([mock_process.stdout], [], []),  # First call: stdout ready
            ([], [], [])   # Second call: nothing ready (process finished)
        ]
        
        result = claude_code("test prompt", structured=True)
        
        assert result.structured == {"result": "success", "data": [1, 2, 3]}
        # Check that --output-format json flag was used
        args = mock_popen.call_args[0][0]
        assert "--output-format" in args
        assert "json" in args

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_claude_code_invalid_json(self, mock_stderr, mock_stdout, mock_select, mock_popen, mock_find_git_root):
        """Test claude_code with invalid JSON output."""
        mock_find_git_root.return_value = "/test/repo"
        # Mock the process
        mock_process = unittest.mock.Mock()
        mock_process.poll.side_effect = [None, 0]  # Running, then finished
        mock_process.returncode = 0
        mock_process.stdout.readline.side_effect = ["invalid json {", ""]
        mock_process.stderr.readline.side_effect = ["", ""]
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        mock_select.side_effect = [
            ([mock_process.stdout], [], []),
            ([], [], [])
        ]
        
        with pytest.raises(Exception, match="Failed to parse JSON output"):
            claude_code("test prompt", structured=True)

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    @unittest.mock.patch('builtins.print')
    def test_claude_code_retry_success(self, mock_print, mock_stderr_stream, mock_stdout_stream, mock_select, mock_popen, mock_find_git_root):
        """Test claude_code retry mechanism."""
        mock_find_git_root.return_value = "/test/repo"
        # Mock first process (fails)
        mock_process1 = unittest.mock.Mock()
        mock_process1.poll.side_effect = [None, 0]
        mock_process1.returncode = 1
        mock_process1.stdout.readline.side_effect = ["", ""]
        mock_process1.stderr.readline.side_effect = ["error", ""]
        mock_process1.stdout.read.return_value = ""
        mock_process1.stderr.read.return_value = ""
        mock_process1.wait.return_value = None
        
        # Mock second process (succeeds)
        mock_process2 = unittest.mock.Mock()
        mock_process2.poll.side_effect = [None, 0]
        mock_process2.returncode = 0
        mock_process2.stdout.readline.side_effect = ["success\n", ""]
        mock_process2.stderr.readline.side_effect = ["", ""]
        mock_process2.stdout.read.return_value = ""
        mock_process2.stderr.read.return_value = ""
        mock_process2.wait.return_value = None
        
        mock_popen.side_effect = [mock_process1, mock_process2]
        
        # Mock select calls: first for process1 (fails), then for process2 (succeeds)
        mock_select.side_effect = [
            # First process (failure)
            ([], [mock_process1.stderr], []),  # First call: stderr ready with error
            ([], [], []),  # Second call: nothing ready (process finishes)
            # Second process (success)  
            ([mock_process2.stdout], [], []),  # Third call: stdout ready with success
            ([], [], [])   # Fourth call: nothing ready (process finishes)
        ]
        
        with unittest.mock.patch('daneel.time.sleep'):
            result = claude_code("test prompt", retries=1)
        
        assert result.stdout == "success\n"
        assert mock_popen.call_count == 2

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_claude_code_timeout(self, mock_stderr_stream, mock_stdout_stream, mock_select, mock_popen, mock_find_git_root):
        """Test claude_code timeout handling."""
        mock_find_git_root.return_value = "/test/repo"
        
        # Mock the process
        mock_process = unittest.mock.Mock()
        # Use side_effect to simulate poll behavior: a few None returns, then finish
        poll_count = [0]
        def mock_poll():
            poll_count[0] += 1
            if poll_count[0] > 2:  # After a couple of iterations, break the loop
                return 0
            return None
        mock_process.poll.side_effect = mock_poll
        mock_process.returncode = 0
        mock_process.stdout.readline.return_value = ""
        mock_process.stderr.readline.return_value = ""
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.wait.side_effect = subprocess.TimeoutExpired("claude", 120)
        mock_process.kill.return_value = None
        mock_popen.return_value = mock_process
        
        mock_select.return_value = ([], [], [])  # No data ready
        
        with pytest.raises(Exception, match="timed out after"):
            claude_code("test prompt", retries=0)

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    def test_claude_code_not_found(self, mock_popen, mock_find_git_root):
        """Test claude_code when claude command is not found."""
        mock_find_git_root.return_value = "/test/repo"
        mock_popen.side_effect = FileNotFoundError()
        
        with pytest.raises(Exception, match="Claude command not found"):
            claude_code("test prompt")

    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_claude_code_with_custom_cwd(self, mock_stderr, mock_stdout, mock_select, mock_popen):
        """Test claude_code with custom working directory."""
        # Mock the process
        mock_process = unittest.mock.Mock()
        mock_process.poll.side_effect = [None, 0]  # Running, then finished
        mock_process.returncode = 0
        mock_process.stdout.readline.side_effect = ["Hello world", ""]
        mock_process.stderr.readline.side_effect = ["", ""]
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        mock_select.side_effect = [
            ([mock_process.stdout], [], []),
            ([], [], [])
        ]
        
        result = claude_code("test prompt", cwd="/custom/path")
        
        assert result.stdout == "Hello world"
        mock_popen.assert_called_once_with(
            ["claude", "-p", "--verbose", "test prompt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/custom/path",
            bufsize=1,
            universal_newlines=True
        )


class TestValidate:
    """Tests for the validate function."""

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.run')
    def test_validate_success(self, mock_run, mock_find_git_root):
        """Test successful validate execution."""
        mock_find_git_root.return_value = "/test/repo"
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout="success",
            stderr=""
        )
        
        def dummy_fail_fn(output):
            return Output("fixed", "")
        
        result = validate("echo success", dummy_fail_fn)
        
        assert result.stdout == "success"
        mock_run.assert_called_once_with(
            "echo success",
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/test/repo"
        )

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.run')
    def test_validate_with_failure_function(self, mock_run, mock_find_git_root):
        """Test validate with failure function."""
        mock_find_git_root.return_value = "/test/repo"
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

    @unittest.mock.patch('daneel.subprocess.run')
    def test_validate_with_custom_cwd(self, mock_run):
        """Test validate with custom working directory."""
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout="success",
            stderr=""
        )
        
        def dummy_fail_fn(output):
            return Output("fixed", "")
        
        result = validate("echo success", dummy_fail_fn, cwd="/custom/path")
        
        assert result.stdout == "success"
        mock_run.assert_called_once_with(
            "echo success",
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/custom/path"
        )


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


class TestMain:
    """Tests for the main function."""

    @unittest.mock.patch('sys.argv', ['daneel.py'])
    @unittest.mock.patch('builtins.print')
    def test_main_no_arguments(self, mock_print):
        """Test main function with no arguments."""
        main()
        
        # Check that usage information is printed
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Daneel - Python helper functions" in call for call in calls)
        assert any("Usage: python daneel.py <action>" in call for call in calls)
        assert any("Available actions: fix_review, implement" in call for call in calls)

    @unittest.mock.patch('sys.argv', ['daneel.py', 'nonexistent'])
    @unittest.mock.patch('builtins.print')
    def test_main_nonexistent_action(self, mock_print):
        """Test main function with non-existent action."""
        main()
        
        # Check that error message is printed
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Action 'nonexistent' not found" in call for call in calls)
        assert any("fix_review" in call for call in calls)
        assert any("implement" in call for call in calls)

    @unittest.mock.patch('sys.argv', ['daneel.py', 'implement'])
    @unittest.mock.patch('importlib.util.spec_from_file_location')
    @unittest.mock.patch('importlib.util.module_from_spec')
    def test_main_successful_action_execution(self, mock_module_from_spec, mock_spec_from_file):
        """Test main function successfully executing an action."""
        # Mock the module loading
        mock_spec = unittest.mock.Mock()
        mock_loader = unittest.mock.Mock()
        mock_spec.loader = mock_loader
        mock_spec_from_file.return_value = mock_spec
        
        # Mock the module with a main function
        mock_module = unittest.mock.Mock()
        mock_main_func = unittest.mock.Mock()
        mock_module.main = mock_main_func
        mock_module_from_spec.return_value = mock_module
        
        main()
        
        # Verify the action module was loaded and main was called
        mock_spec_from_file.assert_called_once()
        mock_loader.exec_module.assert_called_once_with(mock_module)
        mock_main_func.assert_called_once()

    @unittest.mock.patch('sys.argv', ['daneel.py', 'fix_review'])
    @unittest.mock.patch('importlib.util.spec_from_file_location')
    @unittest.mock.patch('builtins.print')
    def test_main_spec_loading_failure(self, mock_print, mock_spec_from_file):
        """Test main function when module spec loading fails."""
        mock_spec_from_file.return_value = None
        
        main()
        
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Could not load action module 'fix_review'" in call for call in calls)

    @unittest.mock.patch('sys.argv', ['daneel.py', 'implement'])
    @unittest.mock.patch('importlib.util.spec_from_file_location')
    @unittest.mock.patch('importlib.util.module_from_spec')
    @unittest.mock.patch('builtins.print')
    def test_main_module_without_main_function(self, mock_print, mock_module_from_spec, mock_spec_from_file):
        """Test main function when action module lacks main() function."""
        # Mock the module loading
        mock_spec = unittest.mock.Mock()
        mock_loader = unittest.mock.Mock()
        mock_spec.loader = mock_loader
        mock_spec_from_file.return_value = mock_spec
        
        # Mock module without main function
        mock_module = unittest.mock.Mock()
        # Create a mock that will return False for hasattr(module, 'main')
        def mock_hasattr(obj, name):
            if name == 'main':
                return False
            return hasattr(type(obj), name)
        
        with unittest.mock.patch('builtins.hasattr', side_effect=mock_hasattr):
            mock_module_from_spec.return_value = mock_module
            
            main()
            
            calls = [call.args[0] for call in mock_print.call_args_list]
            assert any("does not have a main() function" in call for call in calls)

    @unittest.mock.patch('sys.argv', ['daneel.py', 'implement'])
    @unittest.mock.patch('importlib.util.spec_from_file_location')
    @unittest.mock.patch('builtins.print')
    def test_main_import_exception(self, mock_print, mock_spec_from_file):
        """Test main function when module import raises exception."""
        mock_spec_from_file.side_effect = ImportError("Cannot import module")
        
        main()
        
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Error executing action 'implement'" in call for call in calls)
        assert any("Cannot import module" in call for call in calls)

    @unittest.mock.patch('sys.argv', ['daneel.py', 'implement'])
    @unittest.mock.patch('importlib.util.spec_from_file_location')
    @unittest.mock.patch('importlib.util.module_from_spec')
    @unittest.mock.patch('builtins.print')
    def test_main_execution_exception(self, mock_print, mock_module_from_spec, mock_spec_from_file):
        """Test main function when action execution raises exception."""
        # Mock the module loading
        mock_spec = unittest.mock.Mock()
        mock_loader = unittest.mock.Mock()
        mock_spec.loader = mock_loader
        mock_spec_from_file.return_value = mock_spec
        
        # Mock module with main function that raises exception
        mock_module = unittest.mock.Mock()
        mock_main_func = unittest.mock.Mock()
        mock_main_func.side_effect = RuntimeError("Action execution failed")
        mock_module.main = mock_main_func
        mock_module_from_spec.return_value = mock_module
        
        main()
        
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Error executing action 'implement'" in call for call in calls)
        assert any("Action execution failed" in call for call in calls)

    @unittest.mock.patch.object(Path, 'exists')
    @unittest.mock.patch('sys.argv', ['daneel.py', 'test_action'])
    @unittest.mock.patch('builtins.print')
    def test_main_actions_directory_not_found(self, mock_print, mock_exists):
        """Test main function when actions directory doesn't exist."""
        mock_exists.return_value = False
        
        main()
        
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Actions directory not found" in call for call in calls)

    @unittest.mock.patch('sys.argv', ['daneel.py', 'implement'])
    @unittest.mock.patch('importlib.util.spec_from_file_location')
    @unittest.mock.patch('importlib.util.module_from_spec')
    def test_main_with_real_action_paths(self, mock_module_from_spec, mock_spec_from_file):
        """Test main function with real action file paths."""
        # Mock the module loading
        mock_spec = unittest.mock.Mock()
        mock_loader = unittest.mock.Mock()
        mock_spec.loader = mock_loader
        mock_spec_from_file.return_value = mock_spec
        
        # Mock the module with a main function
        mock_module = unittest.mock.Mock()
        mock_main_func = unittest.mock.Mock()
        mock_module.main = mock_main_func
        mock_module_from_spec.return_value = mock_module
        
        main()
        
        # Verify that spec_from_file_location was called with correct parameters
        call_args = mock_spec_from_file.call_args
        assert call_args[0][0] == "actions.implement"  # module name
        assert str(call_args[0][1]).endswith("actions/implement.py")  # file path