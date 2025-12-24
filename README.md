# Daneel

Python helper functions for agentic coding assistants

## Overview

Daneel provides a set of utility functions specifically designed to help agentic coding assistants interact with external tools and manage project state. It includes functions for command execution, YAML file manipulation, and project progress tracking.

## Features

* **Claude Integration**: Execute Claude commands with structured output parsing
* **Command Validation**: Run commands with automatic retry and failure handling
* **YAML Management**: Update YAML files using query-based field selection
* **Progress Tracking**: Calculate completion percentage from markdown checkboxes
* **Robust Error Handling**: Comprehensive timeout and retry mechanisms
* **Nix Integration**: Fully packaged with Nix flakes for reproducible environments

## Installation

### Using Nix Flakes

```bash
# Use in your flake.nix
{
  inputs.daneel.url = "github:your-org/daneel";
  
  # In your packages or devShell
  buildInputs = [ daneel.packages.${system}.default ];
}
```

### Development Environment

```bash
# Enter development shell
nix develop

# Or build the package
nix build
```

## Usage Examples

### Basic Usage

```python
from daneel import Output, claude_code, validate, update_yml, checkbox_progress

# Execute Claude with structured output
result = claude_code("Analyze this code structure", structured=True)
print(result.structured)  # Parsed JSON response

# Validate a build command with automatic retry
def fix_build_error(output):
    print(f"Build failed: {output.stderr}")
    # Implement fix logic here
    return Output("fix attempted", "")

result = validate("npm run build", fix_build_error, retries=3)
print(f"Build output: {result.stdout}")
```

### YAML Configuration Management

```python
# Update nested YAML configurations
update_yml("config.yml", "database.host", "localhost")
update_yml("config.yml", "services.web.ports[0]", "8080:3000")
update_yml("docker-compose.yml", "services.app.environment.NODE_ENV", "production")
```

### Project Progress Tracking

```python
# Track completion of markdown todo lists
progress = checkbox_progress("TODO.md")
print(f"Project completion: {progress:.1%}")

# Use in automation scripts
if progress >= 0.8:
    print("Project is 80% complete, ready for review")
```

### Advanced Command Validation

```python
def smart_fix_function(failed_output):
    """Intelligent error recovery based on failure output."""
    if "permission denied" in failed_output.stderr.lower():
        # Fix permission issues
        subprocess.run(["chmod", "+x", "./script.sh"])
        return Output("Fixed permissions", "")
    elif "missing dependency" in failed_output.stderr.lower():
        # Install missing dependencies
        subprocess.run(["npm", "install"])
        return Output("Installed dependencies", "")
    else:
        return Output("Unknown error", "Could not fix automatically")

# Run tests with automatic error recovery
result = validate("npm test", smart_fix_function, timeout=300, retries=2)
```

## API Reference

### Output

Dataclass representing command execution results.

**Fields:**
- `stdout: str` - Standard output
- `stderr: str` - Standard error  
- `structured: Optional[Dict[str, Any]]` - Parsed JSON data

### claude_code(prompt, structured=False, timeout=120, retries=3)

Execute Claude commands with optional structured output parsing.

**Parameters:**
- `prompt: str` - The prompt to send to Claude
- `structured: bool` - Request and parse JSON output
- `timeout: int` - Command timeout in seconds
- `retries: int` - Number of retry attempts

**Returns:** `Output` object

### validate(cmd, fail_fn, timeout=120, retries=3)

Execute commands with failure handling and automatic retry.

**Parameters:**
- `cmd: str` - Shell command to execute
- `fail_fn: Callable[[Output], Output]` - Function called on failure
- `timeout: int` - Command timeout in seconds  
- `retries: int` - Number of retry attempts

**Returns:** `Output` object

### update_yml(file, field, value)

Update YAML files using query-based field selection.

**Parameters:**
- `file: str` - Path to YAML file
- `field: str` - Query string (e.g., "app.config.debug" or "items[0].name")
- `value: Any` - New value to set

### checkbox_progress(file)

Calculate completion percentage from markdown checkboxes.

**Parameters:**
- `file: str` - Path to markdown file

**Returns:** `float` - Completion percentage (0.0 to 1.0)

## Testing

```bash
# Run all tests
nix develop --command python -m pytest

# Run with coverage
nix develop --command python -m pytest --cov=daneel

# Type checking
nix develop --command mypy daneel.py

# Linting
nix develop --command ruff check daneel.py
```

## Problems Solved

* **Agent Containerization**: Provides standardized interface for tool interaction
* **Progress Tracking**: Automatically track project completion state
* **Prompt Reuse**: Structured output parsing enables consistent agent workflows
* **Multi-agent Support**: Unified interface for different agentic operations
* **Error Recovery**: Robust retry mechanisms with intelligent failure handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `nix develop --command python -m pytest`
6. Submit a pull request

## License

[Add your license information here]
