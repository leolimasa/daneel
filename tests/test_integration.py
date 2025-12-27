"""Integration tests for the complete daneel workflow."""

import json
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

import pytest
import yaml

from daneel import Output, checkbox_progress, claude_code, update_yml, validate


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_end_to_end_yaml_and_progress_tracking(self):
        """Test a complete workflow using YAML updates and progress tracking."""
        # Create a temporary YAML file and markdown file
        yaml_content = {
            "project": {
                "name": "test-project",
                "tasks": [
                    {"name": "task1", "status": "pending"},
                    {"name": "task2", "status": "pending"}
                ]
            }
        }
        
        markdown_content = """
# Project TODO

- [ ] Complete task 1
- [ ] Complete task 2
- [ ] Write tests
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as yaml_file:
            yaml.safe_dump(yaml_content, yaml_file)
            yaml_path = yaml_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as md_file:
            md_file.write(markdown_content)
            md_path = md_file.name
        
        try:
            # Initial progress should be 0%
            initial_progress = checkbox_progress(md_path)
            assert initial_progress == 0.0
            
            # Update YAML to mark first task as completed
            update_yml(yaml_path, "project.tasks[0].status", "completed")
            
            # Verify the update
            with open(yaml_path, 'r') as f:
                updated_yaml = yaml.safe_load(f)
            assert updated_yaml["project"]["tasks"][0]["status"] == "completed"
            assert updated_yaml["project"]["tasks"][1]["status"] == "pending"
            
            # Update markdown to reflect task completion
            updated_markdown = """
# Project TODO

- [x] Complete task 1
- [ ] Complete task 2
- [ ] Write tests
            """
            with open(md_path, 'w') as f:
                f.write(updated_markdown)
            
            # Progress should now be 1/3 = 33.33%
            updated_progress = checkbox_progress(md_path)
            assert abs(updated_progress - 1/3) < 0.001
            
        finally:
            Path(yaml_path).unlink()
            Path(md_path).unlink()

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.run')
    def test_command_validation_with_retry(self, mock_run, mock_find_git_root):
        """Test the validate function with failure and recovery."""
        mock_find_git_root.return_value = "/test/repo"
        # Simulate a command that fails then succeeds
        mock_run.side_effect = [
            unittest.mock.Mock(returncode=1, stdout="", stderr="build failed"),
            unittest.mock.Mock(returncode=0, stdout="build succeeded", stderr="")
        ]
        
        fix_attempts = 0
        def fix_build_error(output):
            nonlocal fix_attempts
            fix_attempts += 1
            assert "build failed" in output.stderr
            # Simulate fixing the error
            return Output("attempted fix", "fixed dependency issue")
        
        with unittest.mock.patch('daneel.time.sleep'):
            result = validate("npm run build", fix_build_error, retries=1)
        
        assert result.stdout == "build succeeded"
        assert fix_attempts == 1
        assert mock_run.call_count == 2

    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_claude_code_with_structured_workflow(self, mock_stderr, mock_stdout, mock_select, mock_popen):
        """Test claude_code function with structured output in a workflow context."""
        # Mock claude returning structured data for a task analysis
        task_analysis = {
            "tasks": [
                {"id": 1, "name": "setup environment", "priority": "high"},
                {"id": 2, "name": "write tests", "priority": "medium"},
                {"id": 3, "name": "deploy", "priority": "low"}
            ],
            "estimated_hours": 8
        }
        
        json_output = json.dumps(task_analysis)
        
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
        
        mock_select.side_effect = [
            ([mock_process.stdout], [], []),
            ([], [], [])
        ]
        
        # Request task analysis from Claude
        result = claude_code("Analyze this project and break it down into tasks", structured=True)
        
        assert result.structured is not None
        assert "tasks" in result.structured
        assert len(result.structured["tasks"]) == 3
        assert result.structured["estimated_hours"] == 8
        
        # Verify the --output-format json flag was used
        args = mock_popen.call_args[0][0]
        assert "--output-format" in args
        assert "json" in args

    def test_complex_yaml_updates(self):
        """Test complex nested YAML updates."""
        complex_yaml = {
            "services": {
                "web": {
                    "image": "nginx:latest",
                    "ports": ["80:8080"],
                    "environment": {
                        "NODE_ENV": "development"
                    }
                },
                "database": {
                    "image": "postgres:13",
                    "environment": {
                        "POSTGRES_DB": "myapp"
                    }
                }
            },
            "networks": ["default"]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.safe_dump(complex_yaml, f)
            temp_path = f.name
        
        try:
            # Update multiple nested fields
            update_yml(temp_path, "services.web.environment.NODE_ENV", "production")
            update_yml(temp_path, "services.web.ports[0]", "80:3000")
            update_yml(temp_path, "services.database.environment.POSTGRES_PASSWORD", "secret123")
            
            # Verify all updates
            with open(temp_path, 'r') as f:
                updated_data = yaml.safe_load(f)
            
            assert updated_data["services"]["web"]["environment"]["NODE_ENV"] == "production"
            assert updated_data["services"]["web"]["ports"][0] == "80:3000"
            assert updated_data["services"]["database"]["environment"]["POSTGRES_PASSWORD"] == "secret123"
            # Ensure existing data is preserved
            assert updated_data["services"]["database"]["image"] == "postgres:13"
            
        finally:
            Path(temp_path).unlink()

    def test_markdown_progress_with_various_formats(self):
        """Test checkbox progress calculation with complex markdown."""
        complex_markdown = """
# Main Project

## Phase 1
- [x] Environment setup
- [x] Initial configuration
- [ ] Documentation

## Phase 2  
* [X] Core implementation (uppercase X)
* [ ] Testing
* [ ] Bug fixes

### Subphase 2.1
- [x] Unit tests
- [x] Integration tests
- [ ] Performance tests

## Notes
This is just regular text with some - [ ] fake checkboxes in code:

```bash
echo "- [ ] not a real checkbox"
```

## Phase 3
- [ ] Deployment
- [ ] Monitoring
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(complex_markdown)
            temp_path = f.name
        
        try:
            progress = checkbox_progress(temp_path)
            # Count: 5 completed out of 11 total checkboxes = 5/11 ≈ 0.4545
            assert abs(progress - 5/11) < 0.001
            
        finally:
            Path(temp_path).unlink()

    @unittest.mock.patch('daneel.find_git_root')
    @unittest.mock.patch('daneel.subprocess.Popen')
    @unittest.mock.patch('daneel.select.select')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('sys.stderr')
    def test_timeout_and_retry_mechanisms(self, mock_stderr_stream, mock_stdout_stream, mock_select, mock_popen, mock_find_git_root):
        """Test timeout and retry mechanisms work across all functions."""
        import subprocess
        
        mock_find_git_root.return_value = "/test/repo"
        
        # Test claude_code timeout
        mock_process = unittest.mock.Mock()
        mock_process.poll.return_value = None  # Never finishes
        mock_process.stdout.readline.return_value = ""
        mock_process.stderr.readline.return_value = ""
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.wait.side_effect = subprocess.TimeoutExpired("claude", 1)
        mock_process.kill.return_value = None
        mock_popen.return_value = mock_process
        
        mock_select.return_value = ([], [], [])  # No data ready
        
        with pytest.raises(Exception, match="timed out after 1 seconds"):
            claude_code("test prompt", timeout=1, retries=0)
        
        # Test validate timeout (validate still uses subprocess.run)
        with unittest.mock.patch('daneel.subprocess.run') as mock_run_validate:
            mock_run_validate.side_effect = subprocess.TimeoutExpired("test", 1)
            
            def dummy_fail_fn(output):
                return Output("fix attempt", "")
            
            with pytest.raises(Exception, match="timed out after 1 seconds"):
                validate("test command", dummy_fail_fn, timeout=1, retries=0)

    def test_error_handling_and_edge_cases(self):
        """Test error handling across all functions."""
        # Test YAML with malformed content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            temp_path = f.name
        
        try:
            with pytest.raises(yaml.YAMLError):
                update_yml(temp_path, "field", "value")
        finally:
            Path(temp_path).unlink()
        
        # Test markdown with non-UTF8 content (create a file with binary content)
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.md', delete=False) as f:
            f.write(b'\xff\xfe- [x] Invalid UTF-8')
            temp_path = f.name
        
        try:
            # Should handle encoding errors gracefully
            with pytest.raises(Exception):
                checkbox_progress(temp_path)
        finally:
            Path(temp_path).unlink()
        
        # Test Output validation
        with pytest.raises(TypeError):
            Output(stdout=None, stderr="")  # type: ignore
        
        with pytest.raises(TypeError):
            Output(stdout="", stderr=None)  # type: ignore