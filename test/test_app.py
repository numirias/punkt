from click.testing import CliRunner
from punkt import cli


def test_nothing():
    assert True

def test_import():
    runner = CliRunner()
    runner.invoke(cli, prog_name='punkt')
