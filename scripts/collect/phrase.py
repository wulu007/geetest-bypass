"""Phrase（短语点选）验证码素材采集。

Usage:
  uv run python scripts/collect/phrase.py                  # 采集 10 张
  uv run python scripts/collect/phrase.py -n 200 -c 8      # 并发 8, 采集 200 张
  uv run python scripts/collect/phrase.py -o resources/collect/phrase

每张图写入 ``resources/collect/phrase/``，文件名沿用远端 hash，已存在的文件自动跳过；
单张失败会重试。文件名带 ``.jpg`` / ``.png`` 后缀，直接用 ``cv2.imread`` 读。
"""

import argparse
import asyncio
from pathlib import Path

from wulu_geetest_bypass import Geetest

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'
RISK_TYPE = 'phrase'

DEFAULT_COUNT = 10
DEFAULT_CONCURRENCY = 5
DEFAULT_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'resources' / 'collect' / 'phrase'


def _save(path: Path, blob: bytes) -> bool:
    """写入 ``blob``，已存在则跳过；返回是否为新增文件。"""
    if path.exists():
        return False
    path.write_bytes(blob)
    return True


async def fetch_one(g: Geetest, out_dir: Path) -> int:
    """拉取一张 phrase 图，返回新增文件数（重复为 0）。"""
    data = await g.load()
    if data['captcha_type'] != RISK_TYPE:
        raise ValueError(f'expected {RISK_TYPE}, got {data["captcha_type"]}')
    blob = await g._load_resource(data['imgs'])
    return int(_save(out_dir / Path(data['imgs']).name, blob))


async def collect(
    count: int,
    out_dir: Path,
    concurrency: int,
    captcha_id: str,
    retry: int = DEFAULT_RETRY,
    delay: float = DEFAULT_RETRY_DELAY,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    g = Geetest(captcha_id=captcha_id, risk_type=RISK_TYPE)

    jobs = iter(range(1, count + 1))
    lock = asyncio.Lock()
    total = 0

    async def worker() -> None:
        nonlocal total
        while (i := await _next_job(jobs, lock)) is not None:
            for attempt in range(1, retry + 1):
                try:
                    added = await fetch_one(g, out_dir)
                except Exception as e:
                    if attempt == retry:
                        print(f'[{i}/{count}] failed ({retry} tries): {e}')
                        break
                    await asyncio.sleep(delay * attempt)
                else:
                    async with lock:
                        total += added
                    print(f'[{i}/{count}] +{added}')
                    break

    await asyncio.gather(*(worker() for _ in range(min(concurrency, count))))
    print(f'done: +{total} -> {out_dir}')


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
        help=f'采集张数 (默认 {DEFAULT_COUNT})',
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
        help=f'单张失败重试次数 (默认 {DEFAULT_RETRY})',
    )
    parser.add_argument(
        '--retry-delay',
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help=f'重试基础间隔秒数 (默认 {DEFAULT_RETRY_DELAY}, 递增)',
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
        )
    )


if __name__ == '__main__':
    main()
