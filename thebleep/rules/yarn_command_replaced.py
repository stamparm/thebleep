import re
from thebleep.utils import for_app, quote_words

regex = re.compile(r'Run "(.*)" instead')


@for_app('yarn', at_least=1)
def match(command):
    return regex.findall(command.output)


def get_new_command(command):
    return quote_words(regex.findall(command.output)[0])
