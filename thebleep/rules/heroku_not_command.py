import re
from thebleep.utils import for_app, quote_words


@for_app('heroku')
def match(command):
    return 'Run heroku _ to run' in command.output


def get_new_command(command):
    return quote_words(re.findall('Run heroku _ to run ([^.]*)',
                                  command.output)[0])
