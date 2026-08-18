import subprocess
from ..utils import memoize, which


brew_available = bool(which('brew'))


@memoize
def get_brew_repository():
    """Where brew keeps its own code, which is not always `brew --prefix`.

    On an Intel Mac and a standard Linux install the repository is a
    `Homebrew` directory inside the prefix; on an Apple Silicon Mac and on a
    git-cloned install the prefix is the repository.

    """
    try:
        return subprocess.check_output(['brew', '--repository'],
                                       universal_newlines=True).strip()
    except Exception:
        return None
