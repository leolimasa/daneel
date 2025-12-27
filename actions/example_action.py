"""Example actions for the pexpect-based daneel system."""


class ActionBase:
    """Base class for command line actions that can be performed on spawned processes."""
    
    def execute(self, spawn) -> None:
        """Execute the action on the spawned process."""
        raise NotImplementedError
    
    def get_name(self) -> str:
        """Return the name of this action."""
        raise NotImplementedError


class ListFilesAction(ActionBase):
    """Action that lists files in the current directory."""
    
    def execute(self, spawn) -> None:
        """Execute the list files action."""
        print("Listing files in current directory...")
        spawn.send("ls -la\n")
    
    def get_name(self) -> str:
        """Return the name of this action."""
        return "List Files"


class CheckGitStatusAction(ActionBase):
    """Action that checks git status."""
    
    def execute(self, spawn) -> None:
        """Check git status in the spawned process."""
        print("Checking git status...")
        spawn.send("git status\n")
    
    def get_name(self) -> str:
        """Return the name of this action."""
        return "Git Status"


class HelpAction(ActionBase):
    """Action that sends help command to the spawned process."""
    
    def execute(self, spawn) -> None:
        """Send help command to the spawned process."""
        print("Sending help command...")
        spawn.send("help\n")
    
    def get_name(self) -> str:
        """Return the name of this action."""
        return "Help"