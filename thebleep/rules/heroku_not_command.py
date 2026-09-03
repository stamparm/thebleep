import re
from thebleep.utils import for_app, quote_words


@for_app('heroku')
def match(command):
    return 'Run heroku _ to run' in command.output


def get_new_command(command):
    found = re.findall('Run heroku _ to run ([^.]+)', command.output)
    return quote_words(found[0]) if found else []
