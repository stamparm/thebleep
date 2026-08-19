# -*- encoding: utf-8 -*-

"""Docker is installed, and nothing is listening on its socket.

    $ docker ps
    Cannot connect to the Docker daemon at unix:///var/run/docker.sock.
    Is the docker daemon running?

Docker 25 and later say it differently:

    failed to connect to the docker API at unix:///var/run/docker.sock; check
    if the path is correct and if the daemon is running: ...

Either way the fix is to start it, and on a machine with systemd that is one
command. Only there: `service docker start`, `open -a Docker` and the rest are
each right somewhere and wrong everywhere else, and a suggestion that starts
nothing is worse than none. So the rule is off unless `systemctl` is on this
machine to run.

The socket being at a path Docker cannot reach is a different problem with the
same message -- a `DOCKER_HOST` pointing somewhere that does not exist -- and
starting the daemon will not fix it. Nothing here can tell the two apart, which
is why the suggestion is shown and confirmed rather than run.

Refs: nvbn/thefuck#1102

"""

from thebleep.utils import for_app, which
from thebleep.shells import shell

# What Docker says, in the two spellings it has used. Lowercased before
# comparing, because the capitalisation has moved between versions too.
CANNOT_CONNECT = (
    'cannot connect to the docker daemon',
    'failed to connect to the docker api',
    'is the docker daemon running',
)


# Named one by one rather than starred out of a tuple: the rule pack reads the
# apps a rule is about straight out of the syntax tree, and `@for_app(*APPS)` is
# a name it cannot resolve -- which makes the rule a candidate for every command
# there is.
@for_app('docker', 'docker-compose', 'podman-docker')
def match(command):
    lowered = command.output.lower()
    return (any(message in lowered for message in CANNOT_CONNECT)
            and which('systemctl') is not None)


def get_new_command(command):
    return shell.and_('sudo systemctl start docker', command.script)
