# -*- encoding: utf-8 -*-

"""Inside a container: run each typo for real, then ask the engine what
`bleep` would offer first. Prints one JSON row per typo."""
import json
import os
import subprocess
import sys

os.environ.setdefault('TB_SHELL', 'bash')
from thebleep.conf import settings  # noqa: E402
settings.init()
from thebleep.corrector import get_corrected_commands  # noqa: E402
from thebleep.types import Command  # noqa: E402
from thebleep.utils import forget_memoized, tool_probes  # noqa: E402

work = sys.argv[1]
for raw in sys.stdin:
    cls, typo, want = json.loads(raw)
    os.chdir(work)
    try:
        p = subprocess.run(['bash', '-c', typo], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                           timeout=20, env=dict(os.environ, LC_ALL='C', LANG='C'))
        out, rc = p.stdout.decode('utf-8', 'replace'), p.returncode
    except subprocess.TimeoutExpired:
        out, rc = '', 'timeout'
    first = None
    if rc != 0 and rc != 'timeout':
        forget_memoized()
        try:
            with tool_probes(True):
                for corrected in get_corrected_commands(Command(typo, out)):
                    first = corrected.script
                    rule = corrected.rule.name if corrected.rule else None
                    break
        except Exception as error:  # a crash is a finding
            first = 'CRASH: %r' % error
    print(json.dumps({'cls': cls, 'typo': typo, 'want': want, 'rc': rc,
                      'first': first,
                      'rule': rule if first and not first.startswith('CRASH')
                      else None,
                      'out': out.strip().splitlines()[:2]}), flush=True)
