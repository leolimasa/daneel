# Objective

Use pyexpect to run a command line program and create reusable "actions" that can send input as string and wait for a specific output.

# Classes

Action: Represents an action that can be performed on the command line program. Methods:
* execute(spawn): Executes the action. The `spawn` parameter is the pexpect spawned process.
* get_name(): Returns the name of the action.

# Functions

Single functions that go into daneel.py

## start(command: List, actions, actions_shortcut) -> pexpect.spawn

Starts a command line program using pexpect and returns the spawned process.
The output should also be displayed in real-time (on the user's screen), so the user can see what is happening and interact if necessary.

`actions` is a list of `Action` objects. When the shortcut specified by actions_shortcut is pressed (by the user), a list of actions is displayed to the user, and the user can select one to execute. The selected action's `execute()` method is called, passing the spawned process as an argument.

## send_input(process: pexpect.spawn, input_str: str) -> None

Sends the specified input string to the spawned process.

## wait_for_output(process: pexpect.spawn, expected_output: str, timeout: int = 30) -> bool

Waits for the specified expected output from the spawned process within the given timeout period. Returns True if the expected output is found, False otherwise.

## load_actions(folder) -> List[Action]

* Finds action python files in the specified folder
* Then loads them dynamically, instantiates all classes in those files that inherit from Action, and returns a list of those objects.

## main()

* Loads actions using load_actions() by looking in:
	* the "actions" subdirectory for the current directory.
	* the "daneel" directory for the git root (if there is a git root)
	* the directory specified by the DANEEL_ACTIONS environment variable (if set)
* Starts a command line program using start() by reading the command from command line arguments.

# Implementation details

* Use the pyexpect library to spawn a command line program.
* Create unit tests for each function to ensure they work as expected.
* Run unit tests to verify the implementation.
* There are unit tests that cover functions that no longer exist. Remove those.
* All types should be properly annotated.
* Test types with mypy to ensure type safety.
* Add typechecking to test.sh
