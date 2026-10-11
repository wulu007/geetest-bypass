from __future__ import annotations

import argparse
import importlib.metadata
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

_ENTRY_POINT_GROUP = 'wulu_geetest_bypass.downloads'

Progress = Callable[[int, int | None], None]


class Downloader(Protocol):
    """The callable a ``wulu_geetest_bypass.downloads`` entry point resolves to."""

    def __call__(
        self, progress: Progress | None = None, *, force: bool = False
    ) -> Path: ...


def discover_downloads() -> dict[str, Downloader]:
    """Collect model downloaders registered through entry points.

    Extensions keep their own CLI and register the same callable here::

        [project.entry-points."wulu_geetest_bypass.downloads"]
        icon = "wulu_geetest_bypass_icon.download:download_model"

    The entry point name is the model name used on the command line. The
    callable returns the local model path, reports progress through
    ``progress(done, total | None)``, and skips the download when the model is
    already cached unless ``force`` is true. A plugin that fails to import stays
    listed and raises its real error when used.
    """
    downloads: dict[str, Downloader] = {}
    for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        try:
            downloads[ep.name] = ep.load()
        except Exception as exc:
            downloads[ep.name] = _broken(ep.name, exc)
    return downloads


def _broken(name: str, exc: Exception) -> Downloader:
    def fail(progress: Progress | None = None, *, force: bool = False) -> Path:
        raise RuntimeError(f'{name}: cannot load downloader: {exc!r}')

    return fail


def _version() -> str:
    return importlib.metadata.version('wulu-geetest-bypass')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='wulu-geetest',
        description=(
            'wulu-geetest-bypass — pure Python Geetest v4 CAPTCHA solver.\n'
            'Models shipped by extensions are downloaded through this command.'
        ),
        epilog=(
            'examples:\n'
            '  wulu-geetest download --list    list the models extensions provide\n'
            '  wulu-geetest download icon      download one (skipped when cached)\n'
            '  wulu-geetest download --all     download every registered model'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {_version()}')
    commands = parser.add_subparsers(dest='command', required=True, title='commands')

    download = commands.add_parser(
        'download',
        help='download solver models shipped by extensions',
        description=(
            'Download the models that installed extensions register through the\n'
            'wulu_geetest_bypass.downloads entry point group. A model is fetched\n'
            'automatically on first use, so this is only needed to prefetch it —\n'
            'for example when baking it into an image.'
        ),
        epilog=(
            'examples:\n'
            '  wulu-geetest download --list\n'
            '  wulu-geetest download icon --force\n'
            '  wulu-geetest download --all --quiet'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    download.add_argument(
        'names',
        nargs='*',
        metavar='NAME',
        help='model name(s) to download; --list shows what is available',
    )
    download.add_argument(
        '-a', '--all', action='store_true', help='download every registered model'
    )
    download.add_argument(
        '-l', '--list', action='store_true', help='list registered models and exit'
    )
    download.add_argument(
        '-f', '--force', action='store_true', help='download even when already cached'
    )
    download.add_argument(
        '-q', '--quiet', action='store_true', help='hide the progress bar'
    )

    args = parser.parse_args(argv)
    if args.command == 'download':
        return _download(args)
    return 0


def _download(args: argparse.Namespace) -> int:
    downloads = discover_downloads()
    if args.list:
        print(
            '\n'.join(sorted(downloads)) or 'no model-downloading extension installed'
        )
        return 0

    names = sorted(downloads) if args.all else args.names
    if not names:
        print(
            'wulu-geetest: nothing to download — pass a NAME, --all, or --list',
            file=sys.stderr,
        )
        return 2

    missing = [name for name in names if name not in downloads]
    if missing:
        available = ', '.join(sorted(downloads)) or 'none'
        print(
            f'wulu-geetest: unknown model {", ".join(missing)}; available: {available}',
            file=sys.stderr,
        )
        return 2

    bar = None if args.quiet or not sys.stderr.isatty() else _Bar()
    failed = 0
    for name in names:
        try:
            path = downloads[name](bar, force=args.force)
        except Exception as exc:
            if bar:
                bar.finish()
            print(f'{name}: {exc}', file=sys.stderr)
            failed += 1
            continue
        if bar:
            bar.finish()
        print(f'{name}: {path}')
    return 1 if failed else 0


class _Bar:
    """Minimal single-line progress bar on stderr."""

    def __init__(self, width: int = 28) -> None:
        self._width = width
        self._dirty = False

    def __call__(self, done: int, total: int | None) -> None:
        if total:
            frac = done / total
            filled = int(frac * self._width)
            line = f'[{"#" * filled}{"." * (self._width - filled)}] {frac:5.1%} {_size(done)}/{_size(total)}'
        else:
            line = f'{_size(done)} downloaded'
        sys.stderr.write(f'\r{line}\033[K')
        sys.stderr.flush()
        self._dirty = True

    def finish(self) -> None:
        if self._dirty:
            sys.stderr.write('\n')
            sys.stderr.flush()
            self._dirty = False


def _size(num: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num < 1024:
            return f'{num:.1f} {unit}'
        num /= 1024
    return f'{num:.1f} TB'
