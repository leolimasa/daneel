# Implementation Plan

## Data Structures

### Output (dataclass)
A dataclass to represent command execution results with the following fields:
- `stdout: str` - Standard output from command execution
- `stderr: str` - Standard error from command execution  
- `structured: Optional[Dict[str, Any]]` - Optional structured data parsed from JSON output

## Functions to be Created

### daneel.py

#### `claude_code(prompt: str, structured: bool = False, timeout: int = 120, retries: int = 3) -> Output`
Executes the "claude" command with the given prompt. When `structured=True`, modifies the prompt to request JSON output and parses the response into the `structured` field. Implements timeout and retry logic with exponential backoff. Raises exception if all retries fail.

#### `validate(cmd: str, fail_fn: Callable[[Output], Output], timeout: int = 120, retries: int = 3) -> Output`
Executes the specified command and if it fails, calls the provided failure function with the command output. The failure function should return an Output object containing corrective actions. Implements timeout and retry logic. Raises exception if all retries fail.
After fail_fn is called, the original command should be retried.

#### `update_yml(file: str, field: str, value: Any) -> None`
Updates YAML files using a query-based approach. Will use the `yq` library or similar to enable JSONPath-like queries for the `field` parameter, allowing flexible updates to nested YAML structures.

#### `checkbox_progress(file: str) -> float`
Parses a markdown file to find checkbox items (`- [ ]` and `- [x]`) and calculates the percentage of completed checkboxes. Returns a float between 0.0 and 1.0 representing completion percentage.

## Build System

### flake.nix
Nix flake configuration that:
- Sets up Python development environment with UV package manager
- Defines a derivation for building the command-line tool
- Exports the tool as a package that can be consumed by other flakes
- Includes all necessary Python dependencies
