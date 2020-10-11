from dataclasses import dataclass
from datetime import datetime
from importlib import util
import os
from pathlib import Path
import shutil
import sys

import click
from click import echo

DEFAULT_PATH = Path('~/.dotfiles')
DEFAULT_CONFIG_PATH = DEFAULT_PATH / 'punkt.conf.py'
DEFAULT_DATA_PATH = DEFAULT_PATH / Path('data')
DEFAULT_BACKUP_PATH = Path('~/.cache/punkt')
BACKUP_DIR_FORMAT = 'backup%Y-%d-%m_%H-%M-%S'


good = lambda s: click.style(s, fg='green')
bad = lambda s: click.style(s, fg='red')
ok = lambda s: click.style(s, fg='yellow')

def fatal(msg):
    echo(bad(f'error: {msg}'))
    sys.exit(1)


@dataclass
class Link:
    _loc: str
    _target: str

    def __repr__(self):
        return f'[{self._loc} -> {self._target}]'

    @property
    def status(self, pretty=False):
        status = self._status()
        if not pretty:
            return status
        raise NotImplementedError()

    def _status(self):
        if self._loc.resolve() == self._target:
            return 'managed'
        if self._loc.is_symlink():
            # symlink.exists() returns False if the symlinkt *target* does not
            # exist. Use os.readlink() to resolve the symlink exactly one level
            if Path(os.readlink(self._loc)) == self._target:
                return 'managed'
            return 'unmanaged'
        if self._loc.exists():
            return 'unmanaged'
        return 'missing'

    @property
    def status_code(self):
        if self._status() == 'managed':
            return 0
        return 1

    def install(self):
        self._loc.symlink_to(self._target)

    def backup(self, backups_dir):
        """Move `path` into the current backup directory."""
        return # TODO
        parent = backups_dir / datetime.now().strftime(BACKUP_DIR_FORMAT)
        parent.mkdir(parents=True, exist_ok=True)
        Path(self._loc).rename(parent / self._loc.name)


class Config:

    def __init__(self):
        self._links = []

    def add_link(self, link, target):
        self._links.append(Link(link, target))

    def add_links(self, link, target):
        link = Path(link).expanduser()
        target = self.spec.data_path / Path(target)
        # assert not link.is_absolute()
        # assert target.is_absolute()
        for path in target.iterdir():
            self.add_link(link / path.name, path)

    def all_links(self):
        yield from self._links


def load_config(path):
    """Load config from given `path` and return config as module object.
    """
    spec = util.spec_from_file_location('config', str(path))
    if spec is None:
        raise OSError('failed to load config')
    conf_spec = util.module_from_spec(spec)
    spec.loader.exec_module(conf_spec)

    conf_spec.data_path = Path(getattr(conf_spec, 'data_path', DEFAULT_DATA_PATH)).expanduser()
    conf_spec.directories = getattr(conf_spec, 'directories', [])
    conf_spec.symlinks = getattr(conf_spec, 'symlinks', [])

    config = Config()
    config.spec = conf_spec
    for target, link in conf_spec.directories:
        config.add_links(link, target)
    # TODO handle explicit symlinks
    echo(f'config loaded from: {path}')
    return config


@click.group()
@click.option('-c', '--config-path', type=click.Path(exists=True),
        default=lambda: str(DEFAULT_CONFIG_PATH.expanduser()))
@click.pass_context
def cli(ctx, config_path):
    try:
        ctx.obj = load_config(config_path)
    except OSError as e:
        ctx.fail(e)
    echo(f'action: {ctx.invoked_subcommand}')


@cli.command(help='add path')
@click.argument('path')
@click.pass_obj
def add(config, path):
    path = Path(path).absolute()
    if not (path.exists() or path.is_symlink()):
        fatal(f'not found: {path}')
    for target_parent, link_parent in config.directories:
        if path.parent == link_parent:
            break
    else:
        # TODO Currently only supporting children of managed directories
        fatal(f'is not a managed directory: {path.parent}')
    target = target_parent / path.name
    if target.exists():
        fatal(f'target already exists: {target}')
    if path.is_symlink() and config.data_path in Path(os.readlink(path)).parents:
        fatal(f'already links into dotfiles: {path} -> {Path(os.readlink(path))}')
    try:
        # TODO use rename
        path.rename(path, target)
    except OSError as e:
        fatal(f'moving failed: {e}')
    echo(f'moved: {path} => {target}')
    try:
        path.symlink_to(target)
    except OSError as e:
        fatal(f'link failed: {e}')
    echo(f'link created: {path} => {target}')


@cli.command(help='check status')
@click.pass_obj
def check(config):
    flaws = 0
    for link in config.all_links():
        status = link.status
        echo(f'\tcheck: {link} -- ', nl=False)
        if link.status_code == 0:
            echo(good(status))
        else:
            echo(bad(status))
            flaws += 1
    sys.exit(flaws and 1)


@cli.command(help='install dotfiles')
@click.option('--dry-run', default=False, is_flag=True)
@click.option('-b', '--backup-path', type=click.Path(),
        default=lambda: str(DEFAULT_BACKUP_PATH.expanduser()))
@click.option('-B', '--no-backup', default=False, is_flag=True)
@click.pass_obj
def install(config, dry_run, backup_path, no_backup):
    echo(f'backup path: {backup_path}')
    for link in config.all_links():
        echo(f'{link}... ', nl=False)
        status = link.status
        if status == 'managed':
            echo(ok('skip (managed)'))
            continue
        if status == 'unmanaged':
            echo('backup... ', nl=False)
            if dry_run:
                echo(ok('dry run '), nl=False)
            else:
                link.backup()
                echo(good('OK '), nl=False)
        echo('create symlink... ', nl=False)
        if dry_run:
            echo(ok('dry run'))
            continue
        link.install()
        echo(good('OK'))


@cli.command(help='uninstall dotfiles')
@click.option('--dry-run', default=False, is_flag=True)
@click.option('-b', '--backup-path', type=click.Path(),
        default=lambda: str(DEFAULT_BACKUP_PATH.expanduser()))
@click.option('-B', '--no-backup', default=False, is_flag=True)
@click.pass_obj
def uninstall(config, dry_run, backup_path, no_backup):
    echo(f'backup path: {backup_path}')
    for link in config.all_links():
        status = link.status
        echo(f'backing up: {link} -- ', nl=False)
        if status == 'missing':
            echo(ok('skip (does not exist)'))
            continue
        if status == 'unmanaged':
            echo(ok('skip (unmanaged)'))
            continue
        if dry_run:
            echo(ok('dry run'))
            continue
        if not no_backup:
            link.backup()
        echo(good('ok'))


if __name__ == '__main__':
    cli() # pylint:disable=no-value-for-parameter
