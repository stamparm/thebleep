import re
from subprocess import Popen, PIPE
from thebleep.utils import memoize, eager, which

npm_available = bool(which('npm'))

# `npm run-script` prints the scripts under two headings, and the difference
# between them matters to different callers. Real npm 10.8.2 output:
#
#     Lifecycle scripts included in t@1.0.0:
#       test
#         z
#       start
#         w
#
#     available via `npm run-script`:
#       build
#         x
#
# A name sits at two spaces; the body of the script it names sits at four.
#
# The ones under the first heading are also npm *commands* -- `npm test` runs
# the `test` script without `npm run` -- which is why `get_scripts` leaves them
# out: `npm_run_script` exists to say "you meant `npm run x`", and `npm test`
# needs no such advice. `get_all_scripts` includes them, because
# `npm_missing_script` is correcting a name that came after `npm run` and there
# every script is a candidate. Missing them there is what let `npm run strat`
# be answered with `npm run watch` instead of `npm run start`.
LIFECYCLE_HEADING = 'Lifecycle scripts included in'
RUN_SCRIPT_HEADING = 'available via `npm run-script`:'
NAME = re.compile(r'^ {2}(\S+)\s*$')


@memoize
def _sections():
    """`(lifecycle, run_script)`, as `npm run-script` lists them."""
    proc = Popen(['npm', 'run-script'], stdout=PIPE)
    found = {LIFECYCLE_HEADING: [], RUN_SCRIPT_HEADING: []}
    heading = None

    for raw in proc.stdout.readlines():
        line = raw.decode('utf-8', 'replace').rstrip('\r\n')

        for candidate in (LIFECYCLE_HEADING, RUN_SCRIPT_HEADING):
            if candidate in line:
                heading = candidate
                break
        else:
            name = NAME.match(line)
            if heading and name:
                found[heading].append(name.group(1))

    return found[LIFECYCLE_HEADING], found[RUN_SCRIPT_HEADING]


@eager
def get_scripts():
    """Scripts that need `npm run` in front of them."""
    return _sections()[1]


@eager
def get_all_scripts():
    """Every script `npm run` accepts, lifecycle ones included."""
    lifecycle, run_script = _sections()
    return run_script + [name for name in lifecycle
                         if name not in run_script]
