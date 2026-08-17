class EmptyCommand(Exception):
    """Raised when empty command passed to `thebleep`."""


class NoRuleMatched(Exception):
    """Raised when no rule matched for some command."""


class ScriptNotInLog(Exception):
    """Script not found in log."""
