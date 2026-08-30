import re
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument

MISTAKE = r'(?<=Terraform has no command named ")([^"]+)(?="\.)'
FIX = r'(?<=Did you mean ")([^"]+)(?="\?)'


@for_app('terraform')
def match(command):
    return re.search(MISTAKE, command.output) and re.search(FIX, command.output)


def get_new_command(command):
    mistake = re.search(MISTAKE, command.output).group(0)
    fix = re.search(FIX, command.output).group(0)
    return replace_argument(command.script, mistake, shell.quote(fix))
