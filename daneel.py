"""Daneel - Python helper functions for agentic coding assistants using pexpect."""

import importlib.util
import inspect
import io
import os
import pexpect  # type: ignore[import-untyped]
import select
import signal
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Any


class Action(ABC):
    """Base class for command line actions that can be performed on spawned processes."""
    
    @abstractmethod
    def execute(self, spawn: pexpect.spawn) -> None:
        """Execute the action on the spawned process.
        
        Args:
            spawn: The pexpect spawned process to operate on
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this action.
        
        Returns:
            String name identifying this action
        """
        pass


def start(command: List[str], actions: List[Action], actions_shortcut: str) -> pexpect.spawn:
    """Start a command line program using pexpect and return the spawned process.
    
    The output is displayed in real-time so the user can see what is happening 
    and interact if necessary. When the specified shortcut is pressed, a list 
    of actions is displayed for user selection.
    
    Args:
        command: List of command arguments to spawn
        actions: List of Action objects available for execution
        actions_shortcut: Keyboard shortcut that triggers action menu
        
    Returns:
        The spawned pexpect process
        
    Raises:
        Exception: If the command cannot be started
    """
    try:
        # Join command list into a single string for pexpect
        cmd_str = ' '.join(command)
        spawn = pexpect.spawn(cmd_str)
        
        # Set window size to match current terminal
        try:
            import shutil
            cols, rows = shutil.get_terminal_size()
            spawn.setwinsize(rows, cols)
        except:
            spawn.setwinsize(24, 80)  # Fallback size
        
        # Custom interact function with action shortcut support
        if actions and actions_shortcut:
            _interact_with_actions(spawn, actions, actions_shortcut)
        else:
            # Standard pexpect interact without action support
            spawn.interact()
        
        return spawn
        
    except Exception as e:
        raise Exception(f"Failed to start command {command}: {e}")


def _interact_with_actions(spawn: pexpect.spawn, actions: List[Action], shortcut: str) -> None:
    """Custom interact function that handles user input and action shortcuts.
    
    Args:
        spawn: The pexpect spawned process
        actions: List of available actions  
        shortcut: Keyboard shortcut that triggers action menu
    """
    import termios
    import tty
    
    try:
        # Check if we have a real terminal (not during testing)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        has_terminal = True
    except (OSError, io.UnsupportedOperation):
        # No real terminal available (e.g., during testing)
        # Fall back to standard interact
        spawn.interact()
        return
    
    try:
        # Set terminal to raw mode for character-by-character input
        tty.setraw(fd)
        
        while spawn.isalive():
            # Use select to check for input from user or output from spawn
            ready, _, _ = select.select([sys.stdin, spawn], [], [], 0.1)
            
            if sys.stdin in ready:
                # Read one character from user
                try:
                    char = sys.stdin.read(1)
                    if char == shortcut:
                        # Restore terminal temporarily for action menu
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                        try:
                            print("\n")  # Add newline before menu
                            show_action_menu(spawn, actions)
                        finally:
                            # Return to raw mode
                            tty.setraw(fd)
                    elif char == '\x03':  # Ctrl+C
                        # Send interrupt to spawned process
                        spawn.sendintr()
                    elif char == '\x04':  # Ctrl+D (EOF)
                        spawn.sendeof()
                    elif char == '\x1a':  # Ctrl+Z
                        # Send suspend signal
                        spawn.kill(signal.SIGTSTP)
                    else:
                        # Forward character to spawned process
                        spawn.send(char)
                except (KeyboardInterrupt, EOFError):
                    break
                    
            if spawn in ready:
                # Read output from spawned process and display it
                try:
                    output = spawn.read_nonblocking(size=1000, timeout=0)
                    if output:
                        sys.stdout.write(output.decode('utf-8', errors='replace'))
                        sys.stdout.flush()
                except pexpect.TIMEOUT:
                    continue
                except pexpect.EOF:
                    break
                    
    finally:
        # Restore original terminal settings if we have them
        if has_terminal:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def send_input(process: pexpect.spawn, input_str: str) -> None:
    """Send the specified input string to the spawned process.
    
    Args:
        process: The pexpect spawned process
        input_str: The string to send to the process
        
    Raises:
        Exception: If sending input fails
    """
    try:
        process.send(input_str)
    except Exception as e:
        raise Exception(f"Failed to send input '{input_str}': {e}")


def wait_for_output(process: pexpect.spawn, expected_output: str, timeout: int = 30) -> bool:
    """Wait for the specified expected output from the spawned process.
    
    Args:
        process: The pexpect spawned process
        expected_output: The output string to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if the expected output is found, False otherwise
    """
    try:
        index = process.expect([expected_output, pexpect.TIMEOUT], timeout=timeout)
        return bool(index == 0)
    except Exception:
        return False


def load_actions(folder: str) -> List[Action]:
    """Load action classes from Python files in the specified folder.
    
    Finds action Python files in the specified folder, loads them dynamically,
    instantiates all classes that inherit from Action, and returns a list of 
    those objects.
    
    Args:
        folder: Path to the folder containing action Python files
        
    Returns:
        List of instantiated Action objects
        
    Raises:
        Exception: If folder doesn't exist or action loading fails
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        raise Exception(f"Actions folder not found: {folder}")
    
    actions = []
    
    try:
        # Find all Python files in the folder
        for py_file in folder_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue  # Skip __init__.py and similar files
                
            # Load the module dynamically
            module_name = f"action_{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
                
            module = importlib.util.module_from_spec(spec)
            # Add the current directory to sys.path temporarily for imports
            current_dir = str(Path.cwd())
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            try:
                spec.loader.exec_module(module)
            finally:
                # Remove the added path
                if current_dir in sys.path:
                    sys.path.remove(current_dir)
            
            # Find all classes that inherit from Action
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a class that has the required methods (duck typing approach)
                if (hasattr(obj, 'execute') and hasattr(obj, 'get_name') and 
                    callable(getattr(obj, 'execute')) and callable(getattr(obj, 'get_name')) and
                    name not in ['Action', 'ActionBase']):  # Skip base classes
                    # Instantiate the action class
                    try:
                        action_instance = obj()
                        actions.append(action_instance)
                    except Exception as e:
                        print(f"Warning: Could not instantiate action {name}: {e}")
                        
    except Exception as e:
        raise Exception(f"Failed to load actions from {folder}: {e}")
    
    return actions


def show_action_menu(spawn: pexpect.spawn, actions: List[Action]) -> None:
    """Display action menu and execute selected action.
    
    Args:
        spawn: The pexpect spawned process
        actions: List of available actions
    """
    if not actions:
        print("\nNo actions available.")
        return
    
    print(f"\nAvailable actions:")
    for i, action in enumerate(actions, 1):
        print(f"{i}. {action.get_name()}")
    
    try:
        selection = input("\nSelect an action (number): ")
        index = int(selection) - 1
        
        if 0 <= index < len(actions):
            actions[index].execute(spawn)
        else:
            print("Invalid selection.")
            
    except (ValueError, KeyboardInterrupt):
        print("\nAction cancelled.")


def find_git_root() -> Optional[str]:
    """Find the root directory of the current git repository.
    
    Returns:
        The absolute path to the root directory of the git repository,
        or None if not in a git repository.
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
        return None


def main() -> None:
    """Main entry point for the daneel CLI.
    
    Loads actions and starts a command line program using command line arguments.
    Actions are loaded from:
    1. "actions" subdirectory of current directory
    2. "daneel" directory in git root (if in a git repository)
    3. Directory specified by DANEEL_ACTIONS environment variable (if set)
    """
    if len(sys.argv) < 2:
        print("Usage: python daneel.py <command> [args...]")
        print("       python -m daneel <command> [args...]")
        return
    
    # Get command from command line arguments
    command = sys.argv[1:]
    
    # Load actions from various sources
    actions = []
    action_sources = []
    
    # Check local actions directory
    if os.path.exists("actions"):
        action_sources.append("actions")
    
    # Check daneel directory in git root
    git_root = find_git_root()
    if git_root:
        daneel_dir = Path(git_root) / "daneel"
        if daneel_dir.exists():
            action_sources.append(str(daneel_dir))
    
    # Check environment variable
    env_actions = os.getenv("DANEEL_ACTIONS")
    if env_actions and os.path.exists(env_actions):
        action_sources.append(env_actions)
    
    # Load actions from all sources
    for source in action_sources:
        try:
            actions.extend(load_actions(source))
        except Exception as e:
            print(f"Warning: Failed to load actions from {source}: {e}")
    
    # Default shortcut key (Ctrl+A might be more practical than a single char)
    actions_shortcut = "\x01"  # Ctrl+A
    
    try:
        # Start the command with loaded actions
        spawn = start(command, actions, actions_shortcut)
        
        # Keep the process running until it exits
        spawn.expect(pexpect.EOF)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()