import re
from thebleep.specific.git import git_support
from thebleep.utils import quote_words


@git_support
def match(command):
    return "push" in command.script and "The upstream branch of your current branch does not match" in command.output


@git_support
def get_new_command(command):
    # Both the remote and the branch in this line come out of the repository, and
    # either may be shell syntax, so the line is repeated word by word rather
    # than verbatim.
    found = re.findall(r'^ +(git push [^\s]+ [^\s]+)', command.output,
                       re.MULTILINE)
    return quote_words(found[0]) if found else []
