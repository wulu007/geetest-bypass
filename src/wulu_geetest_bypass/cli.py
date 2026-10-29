from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from importlib.metadata import entry_points
from pathlib import Path

import pooch
from tqdm import tqdm

ENTRY_POINT_GROUP = 'wulu_geetest_bypass.fetcher'


def discover_fetchers() -> dict[str, pooch.Pooch]:
    fetchers: dict[str, pooch.Pooch] = {}

    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            obj = ep.load()
            fetcher = (
                obj() if callable(obj) and not isinstance(obj, pooch.Pooch) else obj
            )
            if isinstance(fetcher, pooch.Pooch):
                fetchers[ep.name] = fetcher
            else:
                print(
                    f"Warning: Plugin '{ep.name}' does not provide a Pooch instance (skipped).",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Warning: Failed to load plugin '{ep.name}': {e}", file=sys.stderr)
    return fetchers


class ProgressBar:
    def __init__(self, desc: str) -> None:
        self.desc = desc
        self.bar: tqdm | None = None

    def __bool__(self) -> bool:
        return True

    @property
    def total(self) -> int:
        return int(self.bar.total or 0) if self.bar else 0

    @total.setter
    def total(self, value: int) -> None:
        if value:
            self.bar = tqdm(
                desc=self.desc,
                total=value,
                unit='B',
                unit_scale=True,
                leave=True,
                file=sys.stdout,
            )

    def update(self, n: int) -> None:
        if self.bar:
            remaining = self.bar.total - self.bar.n
            if remaining > 0:
                self.bar.update(min(n, remaining))

    def reset(self) -> None:
        pass

    def close(self) -> None:
        if self.bar:
            if self.bar.total and self.bar.n < self.bar.total:
                self.bar.update(self.bar.total - self.bar.n)
            self.bar.close()


def format_size(size_bytes: int | float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}' if unit != 'B' else f'{int(size_bytes)} B'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'


def handle_status(args: argparse.Namespace) -> None:
    fetchers = discover_fetchers()
    if not fetchers:
        print('No model plugins installed.')
        return

    roots = sorted({str(Path(fetcher.abspath)) for fetcher in fetchers.values()})
    print(f'Cache: {", ".join(roots)}\n')

    items: list[tuple[str, str, Path]] = []
    for name, fetcher in fetchers.items():
        for fname in fetcher.registry:
            dest = Path(fetcher.abspath) / fname
            items.append((name, fname, dest))

    width = max((len(fname) for _, fname, _ in items), default=28)
    width = max(width, 28)
    ready_count = 0
    total_bytes = 0

    current = ''
    for plugin, fname, dest in items:
        if plugin != current:
            if current:
                print()
            print(f'[{plugin}]')
            current = plugin

        if dest.is_file():
            ready_count += 1
            size = dest.stat().st_size
            total_bytes += size
            size_str = format_size(size)
            status = 'ready'
        else:
            size_str = '-'
            status = 'missing'

        print(f'  {fname:<{width}} {size_str:>10}   {status}')

    missing_count = len(items) - ready_count
    sep_len = max(width + 22, 50)
    print('-' * sep_len)
    print(
        f'{ready_count}/{len(items)} ready ({format_size(total_bytes)}), {missing_count} missing'
    )


def handle_download(args: argparse.Namespace) -> None:
    fetchers = discover_fetchers()
    if not fetchers:
        sys.exit('Error: No model plugins installed.')

    if args.all or not args.plugin:
        targets = fetchers
    elif args.plugin in fetchers:
        targets = {args.plugin: fetchers[args.plugin]}
    else:
        sys.exit(
            f"Error: Plugin '{args.plugin}' not found. Available: {', '.join(fetchers)}"
        )

    unique_assets: dict[Path, tuple[str, pooch.Pooch, str]] = {}
    for name, fetcher in targets.items():
        for fname in fetcher.registry:
            dest = Path(fetcher.abspath) / fname
            if dest not in unique_assets:
                unique_assets[dest] = (name, fetcher, fname)

    if not unique_assets:
        print('Nothing to do: plugins registered no files.')
        return

    width = max((len(fname) for _, _, fname in unique_assets.values()), default=28)
    width = max(width, 28)
    sep_len = max(width + 22, 50)
    roots = sorted({str(Path(fetcher.abspath)) for fetcher in targets.values()})
    print(f'Cache: {", ".join(roots)}')
    print(f'Syncing {len(unique_assets)} asset(s)...\n')

    downloaded = 0
    downloaded_bytes = 0
    cached = 0
    failed = 0
    started = time.perf_counter()

    current = ''
    is_tty = sys.stdout.isatty()

    for dest, (plugin, fetcher, fname) in unique_assets.items():
        if plugin != current:
            if current:
                print()
            print(f'[{plugin}]')
            current = plugin

        if args.force and dest.is_file():
            dest.unlink()

        if dest.is_file():
            cached += 1
            print(f'  {fname:<{width}} {format_size(dest.stat().st_size):>10}   cached')
            continue

        bar = ProgressBar(f'  {fname:<{width}}') if is_tty else False

        token = os.environ.get('HF_TOKEN')
        headers = {'Authorization': f'Bearer {token.strip()}'} if token else {}
        downloader = pooch.HTTPDownloader(progressbar=bar, headers=headers)

        try:
            # pyrefly: ignore[bad-argument-type]
            fetcher.fetch(fname, downloader=downloader)
            downloaded += 1
            if dest.is_file():
                downloaded_bytes += dest.stat().st_size
            if not is_tty:
                size_str = format_size(dest.stat().st_size) if dest.is_file() else ''
                print(f'  {fname:<{width}} {size_str:>10}   downloaded')
        except Exception as exc:
            failed += 1
            print(f'  {fname:<{width}}   failed: {exc}')

    elapsed = time.perf_counter() - started
    print('-' * sep_len)
    print(
        f'Done: {downloaded} downloaded ({format_size(downloaded_bytes)}), '
        f'{cached} cached, {failed} failed | {elapsed:.1f}s'
    )
    if failed:
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='gt-pull', description='Geetest model asset manager'
    )
    subparsers = parser.add_subparsers(dest='command')

    p_status = subparsers.add_parser('status', help='Show model cache status')
    p_status.set_defaults(handler=handle_status)

    p_dl = subparsers.add_parser('download', help='Download model assets')
    p_dl.add_argument(
        'plugin', nargs='?', help='Plugin name (omit or use --all to sync all)'
    )
    p_dl.add_argument(
        '--all', action='store_true', help='Download all installed plugins'
    )
    p_dl.add_argument('--force', action='store_true', help='Force re-download')
    p_dl.set_defaults(handler=handle_download)

    return parser


def main() -> None:
    pooch.get_logger().setLevel(logging.WARNING)
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, 'handler', None)
    handler(args) if handler else parser.print_help()


if __name__ == '__main__':
    main()
