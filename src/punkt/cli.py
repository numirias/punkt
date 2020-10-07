from datetime import datetime
from pathlib import Path
import sys
import os

import click
import colorama
from colorama import Fore, Style


HERE = Path(__file__).parent.absolute()
DOTFILES_PATH = Path('~/.dotfiles').expanduser()
DOTFILES_SUBPATH = Path('data')
BACKUP_PATH = Path().home() / '.cache/punkt' / \
    datetime.now().strftime('backup%Y-%d-%m_%H-%M-%S')


def good(text):
    return Fore.GREEN + text + Style.RESET_ALL


def bad(text):
    return Fore.RED + text + Style.RESET_ALL


def ok(text):
    return Fore.YELLOW + text + Style.RESET_ALL


def read_config():
    with open(DOTFILES_PATH / 'punkt.conf.py') as f:
        code = f.read()
    exec(code)
    return locals()


def load_config():
    print(f'Backup path: {BACKUP_PATH}')
    config = read_config()
    config['directories'] = [
        (target, Path(link).expanduser()) for
        target, link in config.setdefault('directories', [])
    ]
    config['symlinks'] = [
        (Path(target).expanduser(), Path(link).expanduser()) for
        target, link in config.setdefault('symlinks', [])
    ]
    print('config loaded.')
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
    print(f'symlink "{link}" -> "{target}"... ', end='')
    status = symlink_status(target, link)
    if status == 'managed':
        print(ok('skip (managed)'))
        return
    if status == 'unmanaged':
        print('backup... ', end='')
        if dry_run:
            print(ok('dry run '), end='')
        else:
            backup(link)
            print(good('OK '), end='')
    print('create symlink... ', end='')
    if dry_run:
        print(ok('dry run'))
    else:
        link.symlink_to(target)
        print(good('OK'))


def symlink_pairs(config):
    for source, link_parent in config['directories']:
        print(f'\n=== Handle {source} <- {link_parent} ===\n')
        dotfiles_path = (DOTFILES_PATH / DOTFILES_SUBPATH / source)
        for path in dotfiles_path.iterdir():
            yield (path, link_parent / path.name)
    for target, link in config['symlinks']:
        yield (target, link)


def install_symlinks(config, dry_run):
    for target, link in symlink_pairs(config):
        install_symlink(target, link, dry_run)


@click.group()
def cli():
    pass


@cli.command()
@click.option('--dry-run', default=False, is_flag=True)
def install(dry_run):
    print('Installing dotfiles.')
    config = load_config()
    install_symlinks(config, dry_run)


@cli.command()
def check():
    config = load_config()
    for target, link in symlink_pairs(config):
        status = symlink_status(target, link)
        print(f'check "{link}"... ', end='')
        if status == 'missing':
            print(bad('missing'))
            continue
        if status == 'unmanaged':
            print(bad('unmanaged'))
            continue
        if status == 'managed':
            print(good('managed'))
            continue


@cli.command()
@click.option('--dry-run', default=False, is_flag=True)
def uninstall(dry_run):
    config = load_config()
    for target, link in symlink_pairs(config):
        status = symlink_status(target, link)
        print(f'back up "{link}"... ', end='')
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
        print(good('OK'))


def main():
    colorama.init()
    cli()
    return 0


if __name__ == '__main__':
    sys.exit(main())
