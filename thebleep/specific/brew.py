from ..utils import memoize, tool_output, which


brew_available = bool(which('brew'))


@memoize
def get_brew_repository():
    """Where brew keeps its own code, which is not always `brew --prefix`.

    On an Intel Mac and a standard Linux install the repository is a
    `Homebrew` directory inside the prefix; on an Apple Silicon Mac and on a
    git-cloned install the prefix is the repository.

    """
    # Through `tool_output`, which is where the timeout is.
    found = tool_output(['brew', '--repository']).strip()
    return found or None
