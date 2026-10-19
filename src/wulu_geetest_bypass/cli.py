from __future__ import annotations

import argparse
import os
import sys
from importlib.metadata import entry_points

import pooch

ENTRY_POINT_GROUP = 'wulu_geetest_bypass.fetcher'


def discover_fetchers() -> dict[str, pooch.Pooch]:
    fetchers: dict[str, pooch.Pooch] = {}

    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            obj = ep.load()
            # Support both direct instances and factory callables
            if not isinstance(obj, pooch.Pooch) and callable(obj):
                obj = obj()

            if isinstance(obj, pooch.Pooch):
                fetchers[ep.name] = obj
            else:
                print(
                    f"Warning: Plugin '{ep.name}' does not provide a Pooch instance (skipped).",
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                f"Warning: Failed to load plugin '{ep.name}': {e}",
                file=sys.stderr,
            )

    return fetchers


def format_size(size_bytes: int | float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}' if unit != 'B' else f'{size_bytes} B'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'


def handle_status(args: argparse.Namespace) -> None:
    fetchers = discover_fetchers()
    if not fetchers:
        print('No model plugins installed.')
        return

    print('Model Assets:')

    total_assets = 0
    ready_count = 0
    total_bytes = 0

    for name, fetcher in fetchers.items():
        print(f'\n[{name}]  ({fetcher.path})')
        for fname in fetcher.registry:
            total_assets += 1
            local_file = fetcher.abspath / fname

            if local_file.is_file():
                ready_count += 1
                size = local_file.stat().st_size
                total_bytes += size
                size_str = format_size(size)
                badge = '[+]'
            else:
                size_str = '-'
                badge = '[-]'

            print(f'  {badge} {fname:<24} {size_str:>10}')

    missing_count = total_assets - ready_count
    print('\n' + '-' * 48)
    print(
        f'Summary: {len(fetchers)} plugin(s) | {ready_count}/{total_assets} ready '
        f'({format_size(total_bytes)}) | {missing_count} missing\n'
    )


def handle_download(args: argparse.Namespace) -> None:
    fetchers = discover_fetchers()
    if not fetchers:
        sys.exit('Error: No model plugins installed.')

    if args.all:
        targets = fetchers
    elif args.plugin:
        if args.plugin not in fetchers:
            available = ', '.join(fetchers.keys())
            sys.exit(f"Error: Plugin '{args.plugin}' not found. Available: {available}")
        targets = {args.plugin: fetchers[args.plugin]}
    else:
        sys.exit("Usage: Specify a plugin name or use '--all' to sync all.")

    total = len(targets)
    print(f'Syncing model assets ({total} plugin(s))...')

    for i, (name, fetcher) in enumerate(targets.items(), start=1):
        print(f'\n[{i}/{total}] Plugin: {name}')
        for fname in fetcher.registry:
            local_file = fetcher.abspath / fname

            if args.force and local_file.is_file():
                print(f'  * Overwriting: {fname}')
                local_file.unlink()
            elif local_file.is_file():
                print(f'  - Cached: {fname}')
                continue
            token = os.environ.get('HF_TOKEN')
            headers = {'Authorization': f'Bearer {token.strip()}'} if token else {}
            dl = pooch.HTTPDownloader(progressbar=True, headers=headers)
            # pyrefly: ignore[bad-argument-type]
            fetcher.fetch(fname, downloader=dl)

    print('\nAll assets synced.')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='gt-pull', description='plugin/model manager')
    subparsers = parser.add_subparsers(dest='command')

    p_status = subparsers.add_parser('status', help='Show model cache status')
    p_status.set_defaults(handler=handle_status)

    p_dl = subparsers.add_parser('download', help='Prefetch plugin model assets')
    p_dl.add_argument('plugin', nargs='?', help='Plugin name')
    p_dl.add_argument('--all', action='store_true', help='Fetch all installed plugins')
    p_dl.add_argument('--force', action='store_true', help='Force re-download')
    p_dl.set_defaults(handler=handle_download)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, 'handler', None)
    handler(args) if handler else parser.print_help()


if __name__ == '__main__':
    main()
