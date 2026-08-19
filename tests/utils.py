from thebleep import types
from thebleep.const import DEFAULT_PRIORITY


class Rule(types.Rule):
    def __init__(self, name='', match=lambda *_: True,
                 get_new_command=lambda *_: '',
                 enabled_by_default=True,
                 side_effect=None,
                 priority=DEFAULT_PRIORITY,
                 requires_output=True,
                 path=None):
        super(Rule, self).__init__(name, match, get_new_command,
                                   enabled_by_default, side_effect,
                                   priority, requires_output, path)


class CorrectedCommand(types.CorrectedCommand):
    def __init__(self, script='', side_effect=None, priority=DEFAULT_PRIORITY,
                 rule=None):
        super(CorrectedCommand, self).__init__(
            script, side_effect, priority, rule)
