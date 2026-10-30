"""Word（文字点选）验证码素材采集。

Usage:
  uv run python scripts/collect/word.py                  # 采集 10 组
  uv run python scripts/collect/word.py -n 100 -c 8      # 并发 8, 采集 100 组
  uv run python scripts/collect/word.py --only-ques      # 只要题目文字图标, 跳过背景图
  uv run python scripts/collect/word.py -o resources/collect/word

每组包含 1 张背景图（写入 ``bg/``）与 3~4 张题目文字图标（写入 ``ques/``），
并在 ``meta.jsonl`` 中记录每组背景图与题目的对应关系。
文件名沿用远端 hash，已存在的文件自动跳过；单组失败会重试。
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from wulu_geetest_bypass import Geetest

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'
RISK_TYPE = 'word'
BG_SUBDIR = 'bg'
QUES_SUBDIR = 'ques'

DEFAULT_COUNT = 10
DEFAULT_CONCURRENCY = 5
DEFAULT_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_ONLY_QUES = False
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'resources' / 'collect' / 'word'


def _save(path: Path, blob: bytes) -> bool:
    """写入 ``blob``，已存在则跳过；返回是否为新增文件。"""
    if path.exists():
        return False
    path.write_bytes(blob)
    return True


def _stats(bg: int, ques: int, only_ques: bool) -> str:
    return f'ques +{ques}' if only_ques else f'bg +{bg} ques +{ques}'


async def fetch_group(
    g: Geetest,
    bg_dir: Path,
    ques_dir: Path,
    only_ques: bool = DEFAULT_ONLY_QUES,
) -> tuple[int, int, dict | None]:
    """拉取一组素材，返回 (新增背景图数, 新增题目图标数, 组记录数据)。

    ``only_ques`` 为真时不再请求背景图，只拉取题目文字图标。
    """
    data = await g.load()
    if data['captcha_type'] != RISK_TYPE:
        raise ValueError(f'expected {RISK_TYPE}, got {data["captcha_type"]}')

    ques_urls: list[str] = data['ques']
    if only_ques:
        ques_blobs = await g._load_resources(*ques_urls)
        added_ques = sum(
            _save(ques_dir / Path(u).name, b)
            for u, b in zip(ques_urls, ques_blobs, strict=True)
        )
        return 0, added_ques, None

    bg_url: str = data['imgs']
    bg_blob, *ques_blobs = await g._load_resources(bg_url, *ques_urls)

    bg_name = Path(bg_url).name
    ques_names = [Path(u).name for u in ques_urls]

    added_bg = int(_save(bg_dir / bg_name, bg_blob))
    added_ques = sum(
        _save(ques_dir / name, b)
        for name, b in zip(ques_names, ques_blobs, strict=True)
    )

    record = {
        'lot_number': data.get('lot_number'),
        'bg': bg_name,
        'ques': ques_names,
    }
    return added_bg, added_ques, record


async def collect(
    count: int,
    out_dir: Path,
    concurrency: int,
    captcha_id: str,
    retry: int = DEFAULT_RETRY,
    delay: float = DEFAULT_RETRY_DELAY,
    only_ques: bool = DEFAULT_ONLY_QUES,
    save_meta: bool = True,
) -> None:
    bg_dir, ques_dir = out_dir / BG_SUBDIR, out_dir / QUES_SUBDIR
    ques_dir.mkdir(parents=True, exist_ok=True)
    if not only_ques:
        bg_dir.mkdir(parents=True, exist_ok=True)
    g = Geetest(captcha_id=captcha_id, risk_type=RISK_TYPE)

    meta_path = (out_dir / 'meta.jsonl') if (save_meta and not only_ques) else None

    jobs = iter(range(1, count + 1))
    lock = asyncio.Lock()
    totals = [0, 0]

    async def worker() -> None:
        while (i := await _next_job(jobs, lock)) is not None:
            for attempt in range(1, retry + 1):
                try:
                    bg, ques, record = await fetch_group(g, bg_dir, ques_dir, only_ques)
                except Exception as e:
                    if attempt == retry:
                        print(f'[{i}/{count}] failed ({retry} tries): {e}')
                        break
                    await asyncio.sleep(delay * attempt)
                else:
                    async with lock:
                        totals[0] += bg
                        totals[1] += ques
                        if meta_path and record:
                            with open(meta_path, 'a', encoding='utf-8') as f:
                                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    print(f'[{i}/{count}] {_stats(bg, ques, only_ques)}')
                    break

    await asyncio.gather(*(worker() for _ in range(min(concurrency, count))))
    print(f'done: {_stats(totals[0], totals[1], only_ques)} -> {out_dir}')


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
        '--only-ques',
        action='store_true',
        default=DEFAULT_ONLY_QUES,
        help='仅采集题目文字图标，跳过背景图',
    )
    parser.add_argument(
        '--no-meta',
        action='store_true',
        help='不写入 meta.jsonl 映射文件',
    )
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
    args = parser.parse_args()
    asyncio.run(
        collect(
            count=args.count,
            out_dir=args.out,
            concurrency=args.concurrency,
            captcha_id=args.captcha_id,
            retry=args.retry,
            delay=args.retry_delay,
            only_ques=args.only_ques,
            save_meta=not args.no_meta,
        )
    )


if __name__ == '__main__':
    main()
