import pytest

from thebleep.rules import python_module_error
from thebleep.rules.python_module_error import get_new_command, match
from thebleep.types import Command


@pytest.fixture
def module_error_output(filename, module_name):
    return """Traceback (most recent call last):
  File "{0}", line 1, in <module>
    import {1}
ModuleNotFoundError: No module named '{1}'""".format(
        filename, module_name
    )


@pytest.mark.parametrize(
    "test",
    [
        Command("python hello_world.py", "Hello World"),
        Command(
            "./hello_world.py",
            """Traceback (most recent call last):
  File "hello_world.py", line 1, in <module>
    pritn("Hello World")
NameError: name 'pritn' is not defined""",
        ),
    ],
)
def test_not_match(test):
    assert not match(test)


positive_tests = [
    (
        "python some_script.py",
        "some_script.py",
        "more_itertools",
        "python -m pip install more_itertools && python some_script.py",
    ),
    (
        "python3.12 some_script.py",
        "some_script.py",
        "more_itertools",
        "python3.12 -m pip install more_itertools && python3.12 some_script.py",
    ),
    (
        "/usr/bin/python3 some_script.py",
        "some_script.py",
        "more_itertools",
        "/usr/bin/python3 -m pip install more_itertools"
        " && /usr/bin/python3 some_script.py",
    ),
    (
        "./some_other_script.py",
        "some_other_script.py",
        "a_module",
        "pip install a_module && ./some_other_script.py",
    ),
]


@pytest.mark.parametrize(
    "script, filename, module_name, corrected_script", positive_tests
)
def test_match(script, filename, module_name, corrected_script, module_error_output):
    assert match(Command(script, module_error_output))


@pytest.mark.parametrize(
    "script, filename, module_name, corrected_script", positive_tests
)
def test_get_new_command(
    script, filename, module_name, corrected_script, module_error_output
):
    assert get_new_command(Command(script, module_error_output)) == corrected_script


def test_off_by_default():
    """An import name is not a distribution name.

    `import yaml` wants PyYAML and `import cv2` wants opencv-python; a mistyped
    import turns the suggestion into `pip install <typo>`, fetched from a public
    index and run. The rule is available, but not as a default one-keypress
    correction.

    """
    assert python_module_error.enabled_by_default is False


@pytest.mark.parametrize("filename, module_name", [("s.py", "more_itertools")])
def test_it_installs_into_the_interpreter_that_failed(module_error_output):
    """Not into whichever pip happens to be first on PATH."""
    command = Command("python3.9 s.py", module_error_output)
    assert get_new_command(command).startswith("python3.9 -m pip install")


@pytest.mark.parametrize("filename, module_name", [("s.py", "requests")])
def test_a_hostile_module_name_is_quoted(module_error_output, set_shell):
    from thebleep.shells import Bash

    set_shell(Bash)
    output = module_error_output.replace("requests", "$(touch pwned)")
    assert "'$(touch pwned)'" in get_new_command(Command("python s.py", output))
