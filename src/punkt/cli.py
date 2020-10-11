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


good = lambda s: click.style(s, fg='green')
bad = lambda s: click.style(s, fg='red')
ok = lambda s: click.style(s, fg='yellow')

def fatal(msg):
    echo(bad(f'error: {msg}'))
    sys.exit(1)


def load_config(path):
    """Load config from given `path` and return config as module object.
    """
    spec = util.spec_from_file_location('config', str(path))
    if spec is None:
        raise OSError('failed to load config')
    config = util.module_from_spec(spec)
    spec.loader.exec_module(config)

    config.data_path = Path(getattr(config, 'data_path', DEFAULT_DATA_PATH)).expanduser()
    config.directories = [
        ( config.data_path / Path(target), Path(link).expanduser()) for
        target, link in getattr(config, 'directories', [])
    ]
    config.symlinks = [
        (Path(target).expanduser(), Path(link).expanduser()) for
        target, link in getattr(config, 'symlinks', [])
    ]
    echo(f'config loaded from: {path}')
    return config


def backup(path, target_parent):
    """Move `path` into the current backup directory."""
    target_path = target_parent / datetime.now().strftime('backup%Y-%d-%m_%H-%M-%S')
    target_path.mkdir(parents=True, exist_ok=True)
    Path(path).rename(target_path / path.name)


def symlink_status(target, link):
    if link.resolve() == target:
        return 'managed'
    if link.is_symlink():
        # Note that symlink.exists() returns False if the symlinkt *target*
        # does not exist.
        # Use os.readlink() to resolve the symlink exactly one level
        if Path(os.readlink(link)) == target:
            return 'managed'
        return 'unmanaged'
    if link.exists():
        return 'unmanaged'
    return 'missing'


def install_symlink(target, link, dry_run):
    echo(f'symlink "{link}" -> "{target}"... ', nl=False)
    status = symlink_status(target, link)
    if status == 'managed':
        echo(ok('skip (managed)'))
        return
    if status == 'unmanaged':
        echo('backup... ', nl=False)
        if dry_run:
            echo(ok('dry run '), nl=False)
        else:
            backup(link)
            echo(good('OK '), nl=False)
    echo('create symlink... ', nl=False)
    if dry_run:
        echo(ok('dry run'))
    else:
        link.symlink_to(target)
        echo(good('OK'))


def symlink_pairs(config):
    for target_parent, link_parent in config.directories:
        echo(f'\nhandle symlinks: {target_parent}/* <- {link_parent}/*')
        for path in (config.data_path / target_parent).iterdir():
            yield (path, link_parent / path.name)
    for target, link in config.symlinks:
        yield (target, link)


@click.group()
@click.option('-c', '--config-path', type=click.Path(exists=True), default=lambda: str(DEFAULT_CONFIG_PATH.expanduser()))
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
    for target, link in symlink_pairs(config):
        status = symlink_status(target, link)
        echo(f'\tcheck: {link} -- ', nl=False)
        if status == 'managed':
            echo(good('managed'))
            continue
        flaws += 1
        if status in ['missing', 'unmanaged']:
            echo(bad(status))
    sys.exit(flaws and 1)


@cli.command(help='install dotfiles')
@click.option('--dry-run', default=False, is_flag=True)
@click.option('-b', '--backup-path', type=click.Path(), default=lambda: str(DEFAULT_BACKUP_PATH.expanduser()))
@click.option('-B', '--no-backup', default=False, is_flag=True)
@click.pass_obj
def install(config, dry_run, backup_path, no_backup):
    echo(f'backup path: {backup_path}')
    for target, link in symlink_pairs(config):
        install_symlink(target, link, dry_run)


@cli.command(help='uninstall dotfiles')
@click.option('--dry-run', default=False, is_flag=True)
@click.option('-b', '--backup-path', type=click.Path(), default=lambda: str(DEFAULT_BACKUP_PATH.expanduser()))
@click.option('-B', '--no-backup', default=False, is_flag=True)
@click.pass_obj
def uninstall(config, dry_run, backup_path, no_backup):
    echo(f'backup path: {backup_path}')
    for target, link in symlink_pairs(config):
        status = symlink_status(target, link)
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
            backup(link, backup_path)
        echo(good('ok'))


if __name__ == '__main__':
    cli() # pylint:disable=no-value-for-parameter
