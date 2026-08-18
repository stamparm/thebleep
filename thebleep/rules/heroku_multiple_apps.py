import re
from thebleep.shells import shell
from thebleep.utils import for_app


@for_app('heroku')
def match(command):
    return 'https://devcenter.heroku.com/articles/multiple-environments' in command.output


def get_new_command(command):
    apps = re.findall('([^ ]*) \\([^)]*\\)', command.output)
    return [command.script + ' --app ' + shell.quote(app) for app in apps]
