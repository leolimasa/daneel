# Daneel

Isolated agentic development orchestrator.

## Problems / friction

* Hard to containerize agents 
  * They sometimes need docker
  * They sometimes need an actual browser for testing
  * Privileged containers give too much access 
* Track where each branch / project is in the prompt/dev process
* Reuse prompts easily
* Support multiple agents with a unified interface

## Features

* Standard debian VM image via QEMU. Allows sharing VMs between multiple projects.
* Manages accessing the VM terminal into the current folder.
* Manages viewing VM desktop, if needed.
* Manages exposing VM ports as needed.
* Uses `flakes.nix` to load dev environments inside VMs
* Fires up a prompt INSIDE the vm, with an optional validator command (that also runs inside the vm)
* `daneel.yml` configures the project settings

## Daneel.yml

```yaml

name: My project name

vms:
   default: myvm.yml

# stores the status of the project/branch
status:
  current_task: 0003_implementation
  status: pending-review
  phase: 1
  progress: 83
 
# These are the default values, shown here for visibility
agents:
  claude-code:
      action: claude -p {{.Prompt}}
      interactive: claude
  gemini:
      action:  

```

## VM files

VM files specify QEMU VM settings to run. Uses virtio-fs for fast file access.

```yaml

image: http://....
ram: ...
disk: ...

# Any extra qemu args go here
qemu_args: ...

scripts:
  # Runs this script after creating the VM
  create:
  ...
  
  enter:
  # Runs this bash script every time we enter the vm 
  ...

```

## Action files

Action files specify AI prompts to run. All values are go lang text/template templates, enhanced by sprout.

```yaml
# These will be prompted if not passed as flags like --project_dir=something
arguments: 
  project_name: none
 
# Specifies a VM to run the actions in.
# If not specified, uses the "default" vm from daneel.yml
vm: default

# Sequential list of actions to run
# Variables:
#   output: output for the current action
#   last_output: output from last action
#   pwd: current directory
#   project_dir: directory where `daneel.yml` is located
#   daneel.x: any value from daneel.yml

actions:
  - agent:
       prompt: ...
       agent: claude-code
       timeout: 10
       retries: 3
       
  - validate:
      cmd: test.sh
      agent: claude-code
      prompt: Tests have failed with {{ output }}. Please fix and run again.
      timeout: 10
      retries: 3
     
  # You can immediately call other actions if this one succeeds
  - action: 
      file: anotheraction.yml
      arguments:
	...
    
# These run if ALL actions are successful (optional)
sucess:
  - agent:
      prompt: Update the {{ project_root }}/daneel.yml file status dict with the key "phase" set to the phase that was just implemented

  - validate_daneel_file:
      retries: 3
      prompt: The daneel.yml file is not valid. Here's the output: {{ output }}. Please try again.
      
  - update_progress_from_markdown:
      todo_file: doc/llm/{{.project_name}}/todo.md
      
fail:
  # Same as above, but runs if any actions fail


```

### Actions

**agent**

Calls an agent and passes a prompt.

* prompt: the prompt to be passed.
* agent: agent name.
* timeout: how long to wait until killing the agent
* retries: how many times to retry the prompt if it times out or returns an error

Sets:

* output: output of the call to the agent command
* timed_out: bool whether the action failed due to a timeout

**validate**

Runs a command. If it exit code is not 0, then runs the specified agent with the specified prompt.

* cmd: command to run
* prompt: prompt to run if the command fails
* agent: agent to use for the prompt
* timeout: how long to wait until killing the agent
* retries: how many times to retry the action if it times out or returns an error

## Usage

`daneel status [project_dirs]...`: reads all `daneel.yml` files for all folders listed and displays a table with all status keys as columns.
`daneel action [action_args] [action_file]`: runs an action file
`daneel agent [agent_name]`: runs an agent interactively
`daneel validate`: validates that the daneel.yml file is valid.

**Common flags**

`--daneel_file=path/to/daneel.yml`: specify the daneel file to use (default: daneel.yml in current folder)
`--project_dir=path/to/project`: specify the project directory (default: current folder)
`--vm=vm-name`: specify the vm to use (default: "default" vm from daneel.yml). Set to "local" to run actions locally.

**VM functionality**

`daneel vm enter`: drops into the VM shell
`daneel vm create`: creates a new vm by downloading the image, starting it, then running the create script and saving that as the root snapshot.
`daneel vm save [image_name]`: saves the current snapshot as an image file
`daneel vm start/stop`: start/stop a vm
