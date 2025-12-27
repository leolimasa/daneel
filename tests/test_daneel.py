"""Tests for the pexpect-based daneel module."""

import os
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pexpect
import pytest

from daneel import (
    Action, start, send_input, wait_for_output, load_actions, 
    show_action_menu, find_git_root, main
)


class DummyAction(Action):
    """Dummy action class for testing purposes."""
    
    def __init__(self, name: str = "Test Action"):
        self.name = name
        self.executed = False
        self.spawn_used = None
    
    def execute(self, spawn: pexpect.spawn) -> None:
        """Execute the test action."""
        self.executed = True
        self.spawn_used = spawn
    
    def get_name(self) -> str:
        """Return the name of this action."""
        return self.name


class TestActionClass:
    """Tests for the Action base class."""
    
    def test_action_interface(self):
        """Test that Action is an abstract base class."""
        # Should not be able to instantiate Action directly
        with pytest.raises(TypeError):
            Action()
    
    def test_test_action_implementation(self):
        """Test our DummyAction implementation."""
        action = DummyAction("My Test")
        assert action.get_name() == "My Test"
        assert not action.executed
        
        # Mock a spawn object
        mock_spawn = Mock()
        action.execute(mock_spawn)
        
        assert action.executed
        assert action.spawn_used is mock_spawn


class TestSendInput:
    """Tests for the send_input function."""
    
    def test_send_input_success(self):
        """Test successful send_input execution."""
        mock_spawn = Mock()
        test_input = "test command\\n"
        
        send_input(mock_spawn, test_input)
        
        mock_spawn.send.assert_called_once_with(test_input)
    
    def test_send_input_failure(self):
        """Test send_input with failing spawn."""
        mock_spawn = Mock()
        mock_spawn.send.side_effect = Exception("Send failed")
        
        with pytest.raises(Exception, match="Failed to send input 'test': Send failed"):
            send_input(mock_spawn, "test")


class TestWaitForOutput:
    """Tests for the wait_for_output function."""
    
    def test_wait_for_output_found(self):
        """Test wait_for_output when expected output is found."""
        mock_spawn = Mock()
        mock_spawn.expect.return_value = 0  # First pattern matched
        
        result = wait_for_output(mock_spawn, "expected output", timeout=10)
        
        assert result is True
        mock_spawn.expect.assert_called_once_with(["expected output", pexpect.TIMEOUT], timeout=10)
    
    def test_wait_for_output_timeout(self):
        """Test wait_for_output when timeout occurs."""
        mock_spawn = Mock()
        mock_spawn.expect.return_value = 1  # Timeout pattern matched
        
        result = wait_for_output(mock_spawn, "expected output", timeout=5)
        
        assert result is False
        mock_spawn.expect.assert_called_once_with(["expected output", pexpect.TIMEOUT], timeout=5)
    
    def test_wait_for_output_exception(self):
        """Test wait_for_output when an exception occurs."""
        mock_spawn = Mock()
        mock_spawn.expect.side_effect = Exception("Expect failed")
        
        result = wait_for_output(mock_spawn, "expected output")
        
        assert result is False


class TestLoadActions:
    """Tests for the load_actions function."""
    
    def test_load_actions_folder_not_found(self):
        """Test load_actions with non-existent folder."""
        with pytest.raises(Exception, match="Actions folder not found"):
            load_actions("/nonexistent/folder")
    
    def test_load_actions_empty_folder(self):
        """Test load_actions with empty folder."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = load_actions(temp_dir)
            assert result == []
    
    def test_load_actions_with_valid_actions(self):
        """Test load_actions with folder containing valid action files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test action file
            action_file = Path(temp_dir) / "test_action.py"
            action_file.write_text('''
from daneel import Action
import pexpect

class MyTestAction(Action):
    def execute(self, spawn: pexpect.spawn) -> None:
        pass
    
    def get_name(self) -> str:
        return "My Test Action"
''')
            
            # Mock the module loading to avoid import issues
            with patch('daneel.importlib.util.spec_from_file_location') as mock_spec_from_file, \
                 patch('daneel.importlib.util.module_from_spec') as mock_module_from_spec, \
                 patch('daneel.inspect.getmembers') as mock_getmembers:
                
                # Create mock spec and module
                mock_spec = Mock()
                mock_loader = Mock()
                mock_spec.loader = mock_loader
                mock_spec_from_file.return_value = mock_spec
                
                mock_module = Mock()
                mock_module_from_spec.return_value = mock_module
                
                # Create mock action class
                mock_action_class = Mock()
                mock_action_class.__module__ = f"actions.test_action"
                mock_action_instance = DummyAction("Loaded Action")
                mock_action_class.return_value = mock_action_instance
                
                # Make issubclass work correctly
                def mock_issubclass(cls, base):
                    return cls is mock_action_class and base is Action
                
                with patch('daneel.issubclass', side_effect=mock_issubclass):
                    mock_getmembers.return_value = [("MyTestAction", mock_action_class)]
                    
                    result = load_actions(temp_dir)
                    
                    assert len(result) == 1
                    assert result[0].get_name() == "Loaded Action"


class TestShowActionMenu:
    """Tests for the show_action_menu function."""
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_show_action_menu_valid_selection(self, mock_print, mock_input):
        """Test show_action_menu with valid selection."""
        mock_spawn = Mock()
        actions = [DummyAction("Action 1"), DummyAction("Action 2")]
        mock_input.return_value = "1"
        
        show_action_menu(mock_spawn, actions)
        
        assert actions[0].executed
        assert not actions[1].executed
        assert actions[0].spawn_used is mock_spawn
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_show_action_menu_invalid_selection(self, mock_print, mock_input):
        """Test show_action_menu with invalid selection."""
        mock_spawn = Mock()
        actions = [DummyAction("Action 1")]
        mock_input.return_value = "99"
        
        show_action_menu(mock_spawn, actions)
        
        assert not actions[0].executed
        mock_print.assert_any_call("Invalid selection.")
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_show_action_menu_no_actions(self, mock_print, mock_input):
        """Test show_action_menu with no actions."""
        mock_spawn = Mock()
        actions = []
        
        show_action_menu(mock_spawn, actions)
        
        mock_print.assert_called_with("\nNo actions available.")
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_show_action_menu_keyboard_interrupt(self, mock_print, mock_input):
        """Test show_action_menu with keyboard interrupt."""
        mock_spawn = Mock()
        actions = [DummyAction("Action 1")]
        mock_input.side_effect = KeyboardInterrupt()
        
        show_action_menu(mock_spawn, actions)
        
        assert not actions[0].executed
        mock_print.assert_any_call("\nAction cancelled.")


class TestFindGitRoot:
    """Tests for the find_git_root function."""
    
    @patch('daneel.subprocess.run')
    def test_find_git_root_success(self, mock_run):
        """Test find_git_root when in a git repository."""
        mock_run.return_value.stdout = "/path/to/git/root\n"
        
        result = find_git_root()
        
        assert result == "/path/to/git/root"
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('daneel.subprocess.run')
    def test_find_git_root_not_git_repo(self, mock_run):
        """Test find_git_root when not in a git repository."""
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        
        result = find_git_root()
        
        assert result is None


class TestStart:
    """Tests for the start function."""
    
    @patch('daneel.pexpect.spawn')
    def test_start_basic(self, mock_spawn_class):
        """Test basic start functionality."""
        mock_spawn = Mock()
        mock_spawn_class.return_value = mock_spawn
        
        command = ["echo", "hello"]
        actions = []
        shortcut = "a"
        
        result = start(command, actions, shortcut)
        
        assert result is mock_spawn
        mock_spawn_class.assert_called_once_with("echo hello")
    
    @patch('daneel.pexpect.spawn')
    def test_start_with_actions(self, mock_spawn_class):
        """Test start with actions and shortcut."""
        mock_spawn = Mock()
        mock_spawn_class.return_value = mock_spawn
        
        command = ["bash"]
        actions = [DummyAction("Test")]
        shortcut = "a"
        
        result = start(command, actions, shortcut)
        
        assert result is mock_spawn
        mock_spawn.interact.assert_called_once()
    
    @patch('daneel.pexpect.spawn')
    def test_start_command_failure(self, mock_spawn_class):
        """Test start when command fails to start."""
        mock_spawn_class.side_effect = Exception("Command not found")
        
        with pytest.raises(Exception, match="Failed to start command"):
            start(["nonexistent"], [], "")


class TestMain:
    """Tests for the main function."""
    
    @patch('sys.argv', ['daneel.py'])
    @patch('builtins.print')
    def test_main_no_arguments(self, mock_print):
        """Test main with no arguments."""
        main()
        
        mock_print.assert_any_call("Usage: python daneel.py <command> [args...]")
    
    @patch('sys.argv', ['daneel.py', 'echo', 'hello'])
    @patch('daneel.start')
    @patch('daneel.load_actions')
    @patch('daneel.Path.exists')
    def test_main_with_command(self, mock_exists, mock_load_actions, mock_start):
        """Test main with a command."""
        mock_exists.return_value = False  # No actions directories exist
        mock_load_actions.return_value = []
        mock_spawn = Mock()
        mock_start.return_value = mock_spawn
        
        main()
        
        mock_start.assert_called_once_with(['echo', 'hello'], [], "\x01")
        mock_spawn.expect.assert_called_once_with(pexpect.EOF)
    
    @patch('sys.argv', ['daneel.py', 'test'])
    @patch('daneel.start')  
    @patch('daneel.load_actions')
    @patch('daneel.find_git_root')
    @patch('os.getenv')
    @patch('os.path.exists')
    def test_main_basic_execution(self, mock_exists, mock_getenv, mock_git_root, mock_load_actions, mock_start):
        """Test basic main execution without action loading."""
        mock_exists.return_value = False  # No action directories exist
        mock_git_root.return_value = None  # Not in git repo
        mock_getenv.return_value = None   # No env var
        mock_load_actions.return_value = []
        mock_spawn = Mock()
        mock_start.return_value = mock_spawn
        
        main()
        
        mock_start.assert_called_once_with(['test'], [], "\x01")
        mock_spawn.expect.assert_called_once_with(pexpect.EOF)


# Fix import issues that might occur during testing
import subprocess