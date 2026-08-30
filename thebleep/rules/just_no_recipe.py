# -*- encoding: utf-8 -*-

"""`just buld` -> `just build`, using the project's declared recipes."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


MISSING = re.compile(r'[Jj]ustfile does not contain recipe [`\']([^`\'\r\n]+)')


@for_app('just')
def match(command):
    return MISSING.search(command.output) is not None


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    recipes = project_context.just_recipes()
    if not recipes:
        return []

    return [
        replace_argument_in_command(command, 'just', broken,
                                    shell.quote(recipe))
        for recipe in matching.rank(broken, recipes, limit=3)]
