# Objective

Create helper python functions for agentic coding assistants.

## implementation notes

* create a flakes.nix file on the project root that sets up the python environment and builds a command line program that can be used by other flakes.
* use UV for any dependencies

## daneel.py

Single file that contains the main functions.

### dataclass Output

Dataclass with the output of a command or agent. Fields:

stdout: string - stdout output
stderr: string - stderr output
structured: Optional[map] - optional structured output

### def claude_code(prompt: string, structured=false, timeout=120, retries=3)

Runs the "claude" command passing the prompt as the argument. If structured is True, appends the prompt so that it forces returning in JSON, and then parses that json into the structured map. If parsing fails that's considered a command failure.

The command is only allowed to run up to timeout seconds. If the exit code is not zero, retry up to `retry` times.

If all retries fail, raises an Exception.

Returns an Output.

### def validate(cmd: string, fail_fn: function, timeout=120, retries=3)

Runs the command specified in `cmd`. If it fails, runs the `fail_fn`, which takes the `Output` of the command as an input and is expected to return an Output. The command is only allowed to run up to timeout seconds. If the exit code is not zero, retry up to `retry` times. 

If all retries fail, raises an Exception.

Returns an Output.

### def update_yml(file: string, field, value)

Updates a particular field on a yml file. Be creative here. Research optimal libraries where you can provide some sort of query for what to change. That would be the value for the "field" argument.

### def checkbox_progress(file: string)

Reads the markdown file specified and returns the percentage of checkboxes that are checked.
