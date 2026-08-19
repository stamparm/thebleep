import pytest
from thebleep.rules.kubectl_unknown_command import match, get_new_command
from thebleep.types import Command


# kubectl >= 1.26: single suggestion
output_single = '''error: unknown command "gat" for "kubectl"

Did you mean this?
\tget

'''

# kubectl >= 1.26: multiple suggestions
output_multiple = '''error: unknown command "decsribe" for "kubectl"

Did you mean this?
\tdescribe
\tdelete

'''

# kubectl < 1.26: slightly different wording
output_old = '''error: unknown command "aply" for "kubectl"

Did you mean this?
        apply

'''


@pytest.mark.parametrize('command', [
    Command('kubectl gat pods', output_single),
    Command('kubectl decsribe pod my-pod', output_multiple),
    Command('kubectl aply -f deploy.yaml', output_old)])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('kubectl get pods', ''),
    Command('kubectl get pods', 'NAME   READY   STATUS\nmy-pod   1/1   Running'),
    Command('vim gat', output_single)])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('kubectl gat pods', output_single),
     ['kubectl get pods']),
    (Command('kubectl gat pods -n kube-system', output_single),
     ['kubectl get pods -n kube-system']),
    (Command('kubectl decsribe pod my-pod', output_multiple),
     ['kubectl describe pod my-pod', 'kubectl delete pod my-pod']),
    (Command('kubectl aply -f deploy.yaml', output_old),
     ['kubectl apply -f deploy.yaml'])])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
