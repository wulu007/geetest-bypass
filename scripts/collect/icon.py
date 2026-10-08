"""Icon（图标点选）验证码素材采集。

Usage:
  uv run python scripts/collect/icon.py                  # 采集 10 组
  uv run python scripts/collect/icon.py -n 100 -c 8      # 并发 8, 采集 100 组
  uv run python scripts/collect/icon.py --only-hint      # 只要提示图标, 跳过背景图
  uv run python scripts/collect/icon.py -o resources/collect/icon

每组包含 1 张背景图（写入 ``bg/``）与 3 张提示图标（写入 ``hint/``），
文件名沿用远端 hash，已存在的文件自动跳过；单组失败会重试。
"""

import argparse
import asyncio
from pathlib import Path

from wulu_geetest_bypass import Geetest

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'
RISK_TYPE = 'icon'
BG_SUBDIR = 'bg'
HINT_SUBDIR = 'hint'

DEFAULT_COUNT = 10
DEFAULT_CONCURRENCY = 5
DEFAULT_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_ONLY_HINT = False
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'resources' / 'collect' / 'icon'


def _save(path: Path, blob: bytes) -> bool:
    """写入 ``blob``，已存在则跳过；返回是否为新增文件。"""
    if path.exists():
        return False
    path.write_bytes(blob)
    return True


def _stats(bg: int, hint: int, only_hint: bool) -> str:
    return f'hint +{hint}' if only_hint else f'bg +{bg} hint +{hint}'


async def _save_paths(g: Geetest, paths: list[str], out_dir: Path) -> int:
    """下载 ``paths`` 并按远端 hash 写入 ``out_dir``，返回新增文件数。"""
    blobs = await g._load_resources(*paths)
    return sum(
        _save(out_dir / Path(p).name, b) for p, b in zip(paths, blobs, strict=True)
    )


async def fetch_group(
    g: Geetest,
    bg_dir: Path,
    hint_dir: Path,
    only_hint: bool = DEFAULT_ONLY_HINT,
) -> tuple[int, int]:
    """拉取一组素材，返回 (新增背景图数, 新增提示图标数)。

    ``only_hint`` 为真时不再请求背景图，只拉取提示图标。
    """
    data = await g.load()
    if only_hint:
        return 0, await _save_paths(g, data['ques'], hint_dir)
    bg, hint = await asyncio.gather(
        _save_paths(g, [data['imgs']], bg_dir),
        _save_paths(g, data['ques'], hint_dir),
    )
    return bg, hint


async def collect(
    count: int,
    out_dir: Path,
    concurrency: int,
    captcha_id: str,
    retry: int = DEFAULT_RETRY,
    delay: float = DEFAULT_RETRY_DELAY,
    only_hint: bool = DEFAULT_ONLY_HINT,
) -> None:
    bg_dir, hint_dir = out_dir / BG_SUBDIR, out_dir / HINT_SUBDIR
    hint_dir.mkdir(parents=True, exist_ok=True)
    if not only_hint:
        bg_dir.mkdir(parents=True, exist_ok=True)
    g = Geetest(captcha_id=captcha_id, risk_type=RISK_TYPE)

    jobs = iter(range(1, count + 1))
    lock = asyncio.Lock()
    totals = [0, 0]

    async def worker() -> None:
        while (i := await _next_job(jobs, lock)) is not None:
            for attempt in range(1, retry + 1):
                try:
                    bg, hint = await fetch_group(g, bg_dir, hint_dir, only_hint)
                except Exception as e:
                    if attempt == retry:
                        print(f'[{i}/{count}] failed ({retry} tries): {e}')
                        break
                    await asyncio.sleep(delay * attempt)
                else:
                    async with lock:
                        totals[0] += bg
                        totals[1] += hint
                    print(f'[{i}/{count}] {_stats(bg, hint, only_hint)}')
                    break

    await asyncio.gather(*(worker() for _ in range(min(concurrency, count))))
    print(f'done: {_stats(totals[0], totals[1], only_hint)} -> {out_dir}')


async def _next_job(jobs, lock: asyncio.Lock) -> int | None:
    async with lock:
        return next(jobs, None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '-n',
        '--count',
        type=int,
        default=DEFAULT_COUNT,
        help=f'采集组数 (默认 {DEFAULT_COUNT})',
    )
    parser.add_argument(
        '-c',
        '--concurrency',
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f'并发数 (默认 {DEFAULT_CONCURRENCY})',
    )
    parser.add_argument('-o', '--out', type=Path, default=DEFAULT_OUT, help='输出目录')
    parser.add_argument('--captcha-id', default=CAPTCHA_ID, help='captcha_id')
    parser.add_argument(
        '--retry',
        type=int,
        default=DEFAULT_RETRY,
        help=f'单组失败重试次数 (默认 {DEFAULT_RETRY})',
    )
    parser.add_argument(
        '--retry-delay',
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help=f'重试基础间隔秒数 (默认 {DEFAULT_RETRY_DELAY}, 递增)',
    )
    parser.add_argument(
        '--only-hint',
        action='store_true',
        default=DEFAULT_ONLY_HINT,
        help='只拉取提示图标, 不请求背景图',
    )
    args = parser.parse_args()
    asyncio.run(
        collect(
            count=args.count,
            out_dir=args.out,
            concurrency=args.concurrency,
            captcha_id=args.captcha_id,
            retry=args.retry,
            delay=args.retry_delay,
            only_hint=args.only_hint,
        )
    )


if __name__ == '__main__':
    main()
