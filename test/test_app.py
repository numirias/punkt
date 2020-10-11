from pathlib import Path
import subprocess

from click.testing import CliRunner
from punkt.cli import cli
import pytest


def parse_dir_tree(root, tree, *args):
    from textwrap import dedent
    lines = dedent(tree).split('\n')
    for arg in args:
        lines.replace('%', arg, 1)
    root = path = Path(root)
    named = type('NamedPaths', (object,), {})()
    indents = []
    for line in lines:
        if not line:
            continue
        ind = len(line) - len(line.lstrip())
        diff = -1
        while indents and indents[-1] >= ind:
            indents.pop()
            diff += 1
        indents.append(ind)
        name = line.strip()
        name, content = name.split('=', 1) if '=' in name else (name, '')
        name, var = name.split('$', 1) if '$' in name else (name, '')
        if diff >= 0:
            path = path.parents[diff]
        path = path / name
        if name.endswith('/'):
            path.mkdir(parents=True, exist_ok=True)
        elif content != '!':
            for k, v in named.__dict__.items():
                content = content.replace(f'${k}', str(v))
            path.write_text(content)
        if var:
            named.__dict__[var] = path
    return named


@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mockenv(tmp_path, monkeypatch):
    test_home = tmp_path / 'me'
    test_home.mkdir()
    monkeypatch.setenv('HOME', str(test_home))


def test_nothing():
    assert True

def test_invoke_from_shell():
    assert subprocess.run(['punkt', '--help']).returncode == 0

def test_import(runner):
    assert runner.invoke(cli).exit_code == 0


@pytest.mark.usefixtures('mockenv')
class TestFeatures:

    _tree = '''
    me/$lhome
        .dotfiles/
            data/
                home/$rhome
                    .foo$rfoo=foo
            punkt.conf.py$config=directories = [("$rhome", "$lhome")]
        .foo$lfoo=!
    '''

    def test_check(self, tmp_path, runner):
        def run(*args):
            return runner.invoke(cli, [*args, 'check'])
        p = parse_dir_tree(tmp_path, self._tree)

        res = run()
        assert ' missing' in res.output
        assert res.exit_code > 0

        p.lfoo = p.lhome / '.foo'
        p.lfoo.write_text('bar')
        res = run()
        assert ' unmanaged' in res.output
        assert res.exit_code > 0

        p.lfoo.unlink()
        p.lfoo.symlink_to(p.rfoo)
        res = run()
        assert ' managed' in res.output
        assert res.exit_code == 0

        new_config = p.config.with_name('alt.conf.py')
        p.config.rename(new_config)
        res = run()
        assert res.exit_code > 0

        res = run('-c', str(new_config))
        assert res.exit_code == 0

    def test_install(self, tmp_path, runner):
        p = parse_dir_tree(tmp_path, self._tree)

        assert not p.lfoo.exists()

        res = runner.invoke(cli, ['install'])
        assert res.exit_code == 0
        assert p.lfoo.exists()
        assert 'skip' not in res.output

        res = runner.invoke(cli, ['install'])
        assert res.exit_code == 0
        assert p.lfoo.exists()
        assert 'skip' in res.output

        # res = runner.invoke(cli, ['uninstall'])
        # assert res.exit_code == 0
        # assert not lfoo.exists()
        # assert 'skip' not in res.output
