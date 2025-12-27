"""Daneel - Python helper functions for agentic coding assistants."""

import importlib.util
import json
import re
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List

import yaml  # type: ignore[import-untyped]


@dataclass
class Output:
    """Dataclass representing the output of a command or agent execution.
    
    Attributes:
        stdout: Standard output from command execution
        stderr: Standard error from command execution 
        structured: Optional structured data parsed from JSON output
    """
    stdout: str
    stderr: str
    structured: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate that stdout and stderr are strings."""
        if not isinstance(self.stdout, str):
            raise TypeError("stdout must be a string")
        if not isinstance(self.stderr, str):
            raise TypeError("stderr must be a string")
        if self.structured is not None and not isinstance(self.structured, dict):
            raise TypeError("structured must be a dictionary or None")


def claude_code(
    prompt: str, 
    structured: bool = False, 
    timeout: int = 30 * 60, 
    retries: int = 3,
    cwd: Optional[str] = None
) -> Output:
    """Execute the 'claude' command with the given prompt.
    
    Args:
        prompt: The prompt to send to Claude
        structured: If True, request JSON output and parse it
        timeout: Maximum execution time in seconds
        retries: Number of retry attempts on failure
        cwd: Working directory for command execution (uses find_git_root if None)
        
    Returns:
        Output object with command results
        
    Raises:
        Exception: If all retries fail or command times out
    """
    command = ["claude", "-p", "--verbose"]

    if structured:
        command = command + ["--output-format", "json"]
    
    working_dir = cwd or find_git_root()
    
    for attempt in range(retries + 1):
        try:
            process = subprocess.Popen(
                command + [prompt],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=working_dir,
                bufsize=1,
                universal_newlines=True
            )
            
            stdout_lines = []
            stderr_lines = []
            
            # Stream output in real-time
            
            while process.poll() is None:
                # Use select to check for available data without blocking
                ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                
                for stream in ready:
                    if stream == process.stdout:
                        line = stream.readline()
                        if line:
                            stdout_lines.append(line)
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    elif stream == process.stderr:
                        line = stream.readline()
                        if line:
                            stderr_lines.append(line)
                            sys.stderr.write(line)
                            sys.stderr.flush()
            
            # Read any remaining output
            remaining_stdout = process.stdout.read()
            remaining_stderr = process.stderr.read()
            
            if remaining_stdout:
                stdout_lines.append(remaining_stdout)
                sys.stdout.write(remaining_stdout)
                sys.stdout.flush()
            
            if remaining_stderr:
                stderr_lines.append(remaining_stderr)
                sys.stderr.write(remaining_stderr)
                sys.stderr.flush()
            
            # Wait for process to complete
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise Exception(f"Command timed out after {timeout} seconds")
            
            stdout_text = ''.join(stdout_lines)
            stderr_text = ''.join(stderr_lines)
            
            if process.returncode == 0:
                output = Output(
                    stdout=stdout_text,
                    stderr=stderr_text
                )
                
                if structured:
                    try:
                        output.structured = json.loads(stdout_text.strip())
                    except json.JSONDecodeError as e:
                        raise Exception(f"Failed to parse JSON output: {e}")
                
                return output
            
            if attempt < retries:
                print(f"Attempt {attempt + 1} failed, retrying...")
                # Exponential backoff
                time.sleep(2 ** attempt)
                continue
                
        except FileNotFoundError:
            raise Exception("Claude command not found")
        except Exception as e:
            if "timed out" in str(e):
                if attempt < retries:
                    print(f"Attempt {attempt + 1} timed out, retrying...")
                    time.sleep(2 ** attempt)
                    continue
                raise e
            else:
                raise e
    
    raise Exception(f"Command failed after {retries + 1} attempts")


def validate(
    cmd: str,
    fail_fn: Callable[[Output], Output],
    timeout: int = 120,
    retries: int = 3,
    cwd: Optional[str] = None
) -> Output:
    """Execute a command and call fail_fn if it fails, then retry.
    
    Args:
        cmd: Command to execute
        fail_fn: Function to call on failure, takes Output and returns Output
        timeout: Maximum execution time in seconds
        retries: Number of retry attempts on failure
        cwd: Working directory for command execution (uses find_git_root if None)
        
    Returns:
        Output object with final command results
        
    Raises:
        Exception: If all retries fail or command times out
    """
    working_dir = cwd or find_git_root()
    
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir
            )
            
            output = Output(
                stdout=result.stdout,
                stderr=result.stderr
            )
            
            if result.returncode == 0:
                return output
            
            if attempt < retries:
                # Call failure function and retry
                fail_fn(output)  # Call failure function to potentially fix the issue
                time.sleep(2 ** attempt)
                continue
                
        except subprocess.TimeoutExpired:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise Exception(f"Command timed out after {timeout} seconds")
    
    raise Exception(f"Command failed after {retries + 1} attempts")


def update_yml(file: str, field: str, value: Any) -> None:
    """Update a field in a YAML file using query-based field selection.
    
    Args:
        file: Path to the YAML file
        field: Query string for the field to update (e.g., 'key.subkey[0].field')
        value: New value to set
        
    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        yaml.YAMLError: If the YAML file is malformed
        ValueError: If the field query is invalid
    """
    file_path = Path(file)
    
    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file}")
    
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML file: {e}")
    
    # Parse field query and update nested structure
    keys = field.split('.')
    current = data
    
    try:
        # Navigate to the parent of the target field
        for key in keys[:-1]:
            if '[' in key and ']' in key:
                # Handle array indexing like 'items[0]'
                base_key, index_str = key.split('[', 1)
                index = int(index_str.rstrip(']'))
                if base_key not in current:
                    current[base_key] = []
                while len(current[base_key]) <= index:
                    current[base_key].append({})
                current = current[base_key][index]
            else:
                if key not in current:
                    current[key] = {}
                current = current[key]
        
        # Set the final value
        final_key = keys[-1]
        if '[' in final_key and ']' in final_key:
            base_key, index_str = final_key.split('[', 1)
            index = int(index_str.rstrip(']'))
            if base_key not in current:
                current[base_key] = []
            while len(current[base_key]) <= index:
                current[base_key].append(None)
            current[base_key][index] = value
        else:
            current[final_key] = value
            
    except (KeyError, ValueError, IndexError) as e:
        raise ValueError(f"Invalid field query '{field}': {e}")
    
    try:
        with open(file_path, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to write YAML file: {e}")


def checkbox_progress(file: str) -> float:
    """Calculate the percentage of completed checkboxes in a markdown file.
    
    Args:
        file: Path to the markdown file
        
    Returns:
        Float between 0.0 and 1.0 representing completion percentage
        
    Raises:
        FileNotFoundError: If the markdown file doesn't exist
    """
    file_path = Path(file)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {file}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise Exception(f"Failed to read markdown file: {e}")
    
    # Find all checkbox patterns: - [ ] and - [x] (with various spacing)
    # REVIEW: checkbox patterns should also include * [ ] and * [x] and be case insensitive
    checkbox_pattern = r'^\s*[-*]\s*\[([x\s])\]'
    matches = re.findall(checkbox_pattern, content, re.MULTILINE | re.IGNORECASE)
    
    if not matches:
        return 0.0
    
    completed = sum(1 for match in matches if match.lower().strip() == 'x')
    total = len(matches)
    
    return completed / total

def find_git_root() -> str:
    """Find the root directory of the current git repository.
    
    Returns:
        The absolute path to the root directory of the git repository.
        
    Raises:
        Exception: If the current directory is not inside a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        raise Exception("Not inside a git repository")

def changed_git_files() -> List[str]:
    """Get a list of files changed in the current git repository.
    
    Returns:
        A list of file paths that have been changed.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.strip().splitlines()
        return [file for file in files if file]
    except subprocess.CalledProcessError:
        raise Exception("Failed to get changed git files") 

def main() -> None:
    """Main entry point for the daneel command-line tool."""
    if len(sys.argv) < 2:
        print("Daneel - Python helper functions for agentic coding assistants")
        print("Usage: python daneel.py <action>")
        print("Available actions: fix_review, implement")
        return
    
    action = sys.argv[1]

    # xxx If DANEEL_PATH is set, OR there is a daneel path in the current git repo, use that path instead. Otherwise use the actions_dir below.
    actions_dir = Path(__file__).parent / "actions"
    
    if not actions_dir.exists():
        print(f"Error: Actions directory not found: {actions_dir}")
        return
    
    action_file = actions_dir / f"{action}.py"
    
    if not action_file.exists():
        print(f"Error: Action '{action}' not found. Available actions:")
        for py_file in actions_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                print(f"  - {py_file.stem}")
        return
    
    try:
        spec = importlib.util.spec_from_file_location(f"actions.{action}", action_file)
        if spec is None or spec.loader is None:
            print(f"Error: Could not load action module '{action}'")
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, 'main'):
            module.main()
        else:
            print(f"Error: Action module '{action}' does not have a main() function")
    except Exception as e:
        print(f"Error executing action '{action}': {e}")


if __name__ == "__main__":
    main()
