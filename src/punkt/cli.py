from datetime import datetime
from importlib import util
import os
from pathlib import Path
import shutil
import sys

import click
import colorama
from colorama import Fore, Style


HERE = Path(__file__).parent.absolute()
DOTFILES_PATH = Path('~/.dotfiles').expanduser()
DOTFILES_DATA_PATH = DOTFILES_PATH / Path('data')
BACKUP_PATH = Path().home() / '.cache/punkt' / \
    datetime.now().strftime('backup%Y-%d-%m_%H-%M-%S')

print = click.echo

def colorize(s, color):
    return color + str(s) + Style.RESET_ALL

good = lambda s: colorize(s, Fore.GREEN)
bad = lambda s: colorize(s, Fore.RED)
ok = lambda s: colorize(s, Fore.YELLOW)

def fatal(msg):
    print(bad(f'error: {msg}'))
    exit(1)

def load_config(config_path):
    if not Path(config_path).exists():
        raise FileNotFoundError('config path not found')

    spec = util.spec_from_file_location('config', config_path)
    if spec is None:
        raise OSError('failed to load config')
    config = util.module_from_spec(spec)
    spec.loader.exec_module(config)

    config.directories = [
        (DOTFILES_DATA_PATH / Path(target), Path(link).expanduser()) for
        target, link in getattr(config, 'directories', [])
    ]
    config.symlinks = [
        (Path(target).expanduser(), Path(link).expanduser()) for
        target, link in getattr(config, 'symlinks', [])
    ]
    print(f'config loaded from: {config_path}')
    return config


def backup(target):
    """Move `target` into the current backup directory."""
    BACKUP_PATH.mkdir(parents=True, exist_ok=True)
    Path(target).rename(BACKUP_PATH / target.name)


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
    print(f'symlink "{link}" -> "{target}"... ', nl=False)
    status = symlink_status(target, link)
    if status == 'managed':
        print(ok('skip (managed)'))
        return
    if status == 'unmanaged':
        print('backup... ', nl=False)
        if dry_run:
            print(ok('dry run '), nl=False)
        else:
            backup(link)
            print(good('OK '), nl=False)
    print('create symlink... ', nl=False)
    if dry_run:
        print(ok('dry run'))
    else:
        link.symlink_to(target)
        print(good('OK'))


def symlink_pairs(config):
    for target_parent, link_parent in config.directories:
        print(f'\nhandle symlinks: {target_parent}/* <- {link_parent}/*')
        for path in (DOTFILES_DATA_PATH / target_parent).iterdir():
            yield (path, link_parent / path.name)
    for target, link in config.symlinks:
        yield (target, link)


@click.group()
@click.option('-c', '--config', default=DOTFILES_PATH / 'punkt.conf.py')
@click.pass_context
def cli(ctx, config):
    try:
        ctx.obj = load_config(config)
    except OSError as e:
        ctx.fail(e)
    print(f'action: {ctx.invoked_subcommand}')


@cli.command(help='add path')
@click.argument('path')
@click.pass_obj
def add(config, path):
    path = Path(path).expanduser().absolute()
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
    if path.is_symlink() and DOTFILES_DATA_PATH in Path(os.readlink(path)).parents:
        fatal(f'already links into dotfiles: {path} -> {Path(os.readlink(path))}')
    try:
        dest = shutil.move(str(path), str(target_parent))
    except OSError as e:
        fatal(f'moving failed: {e}')
    print(f'moved: {path} => {dest}')
    try:
        path.symlink_to(target)
    except OSError as e:
        fatal(f'link failed: {e}')
    print(f'link created: {path} => {target}')



@cli.command(help='check status')
@click.pass_obj
def check(config):
    for target, link in symlink_pairs(config):
        status = symlink_status(target, link)
        print(f'\tcheck: {link} -- ', nl=False)
        if status == 'missing':
            print(bad('missing'))
            continue
        if status == 'unmanaged':
            print(bad('unmanaged'))
            continue
        if status == 'managed':
            print(good('managed'))
            continue


@cli.command(help='install dotfiles')
@click.pass_obj
@click.option('--dry-run', default=False, is_flag=True)
def install(config, dry_run):
    print(f'backup path: {BACKUP_PATH}')
    for target, link in symlink_pairs(config):
        install_symlink(target, link, dry_run)


@cli.command(help='uninstall dotfiles')
@click.option('--dry-run', default=False, is_flag=True)
@click.pass_obj
def uninstall(config, dry_run):
    config = load_config()
    print(f'backup path: {BACKUP_PATH}')
    for target, link in symlink_pairs(config):
        status = symlink_status(target, link)
        print(f'backing up: {link} -- ', nl=False)
        if status == 'missing':
            print(ok('skip (does not exist)'))
            continue
        if status == 'unmanaged':
            print(ok('skip (unmanaged)'))
            continue
        if dry_run:
            print(ok('dry run'))
            continue
        backup(link)
        print(good('ok'))


def main():
    colorama.init()
    cli() # pylint:disable=no-value-for-parameter
    return 1


if __name__ == '__main__':
    sys.exit(main())
