import json

import pytest
from thebleep.specific.npm import get_scripts

run_script_stdout = b'''
Lifecycle scripts included in code-view-web:
  test
    jest

available via `npm run-script`:
  build
    cp node_modules/ace-builds/src-min/ -a resources/ace/ && webpack --progress --colors -p --config ./webpack.production.config.js
  develop
    cp node_modules/ace-builds/src/ -a resources/ace/ && webpack-dev-server --progress --colors
  watch-test
    jest --verbose --watch

'''


@pytest.mark.usefixtures('no_memoize')
def test_get_scripts(mocker):
    mocker.patch(
        'thebleep.specific.npm.tool_lines',
        return_value=run_script_stdout.decode('utf-8').splitlines())
    assert get_scripts() == ['build', 'develop', 'watch-test']


@pytest.mark.usefixtures('no_memoize')
def test_get_scripts_reads_the_manifest_without_running_npm(
        tmpdir, monkeypatch, mocker):
    tmpdir.join('package.json').write(json.dumps({'scripts': {
        'build': 'true', 'test': 'true', 'deploy': 'true'}}))
    monkeypatch.chdir(tmpdir)
    probe = mocker.patch('thebleep.specific.npm.tool_lines')

    assert get_scripts() == ['build', 'deploy']
    probe.assert_not_called()
