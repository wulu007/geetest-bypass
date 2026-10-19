"""Nine（九宫格）验证码素材采集。

Usage:
  uv run python scripts/collect/nine.py                  # 采集 100 组
  uv run python scripts/collect/nine.py -n 1000 -c 8     # 并发 8, 采集 1000 组
  uv run python scripts/collect/nine.py --per-prompt 50  # 每个 prompt 最多留 50 张背景图
  uv run python scripts/collect/nine.py -o resources/collect/nine

prompt 是有限集合（同一批图标反复出现），所以按 prompt 分组：

  prompt/<prompt_md5>.<ext>          所有 prompt，去重后平铺
  bg/<prompt_md5>/<bg_md5>.<ext>     背景图，按 prompt 分组

文件名是图片内容的 md5，已存在的文件自动跳过；单组失败会重试。
"""

import argparse
import asyncio
import hashlib
from pathlib import Path

from wulu_geetest_bypass import Geetest

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'
RISK_TYPE = 'nine'
PROMPT_SUBDIR = 'prompt'
BG_SUBDIR = 'bg'
_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}

DEFAULT_COUNT = 100
DEFAULT_CONCURRENCY = 5
DEFAULT_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_PER_PROMPT = 0
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'resources' / 'collect' / 'nine'


def _digest(blob: bytes) -> str:
    return hashlib.md5(blob).hexdigest()


def _save(directory: Path, url: str, blob: bytes) -> bool:
    """按内容 md5 写入 ``directory``，已存在则跳过；返回是否为新增文件。"""
    path = directory / f'{_digest(blob)}{Path(url).suffix or ".png"}'
    if path.exists():
        return False
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return True


def _count(directory: Path) -> int:
    """只数图片：同目录下的标注 json 不算（X-AnyLabeling 就写在旁边）。"""
    if not directory.is_dir():
        return 0
    return sum(1 for f in directory.iterdir() if f.suffix.lower() in _IMAGE_SUFFIXES)


async def fetch_group(
    g: Geetest,
    prompt_dir: Path,
    bg_root: Path,
    per_prompt: int = DEFAULT_PER_PROMPT,
) -> tuple[int, int, bool]:
    """拉取一组素材，返回 (新增 prompt 数, 新增背景图数, 是否因分组已满而跳过)。

    ``per_prompt`` 大于 0 时，某个 prompt 的背景图已经够数就不再下载背景图，
    用来防止「采集量大了以后全挤在少数几个 prompt 上」。
    """
    data = await g.load()
    urls = data['ques']
    prompts = await g._load_resources(*urls)
    added_prompt = sum(
        _save(prompt_dir, url, blob) for url, blob in zip(urls, prompts, strict=True)
    )

    group = bg_root / _digest(prompts[0])
    if per_prompt and _count(group) >= per_prompt:
        return added_prompt, 0, True

    added_bg = int(_save(group, data['imgs'], await g._load_resource(data['imgs'])))
    return added_prompt, added_bg, False


async def collect(
    count: int,
    out_dir: Path,
    concurrency: int,
    captcha_id: str,
    retry: int = DEFAULT_RETRY,
    delay: float = DEFAULT_RETRY_DELAY,
    per_prompt: int = DEFAULT_PER_PROMPT,
) -> None:
    prompt_dir, bg_root = out_dir / PROMPT_SUBDIR, out_dir / BG_SUBDIR
    prompt_dir.mkdir(parents=True, exist_ok=True)
    bg_root.mkdir(parents=True, exist_ok=True)
    g = Geetest(captcha_id=captcha_id, risk_type=RISK_TYPE)

    jobs = iter(range(1, count + 1))
    lock = asyncio.Lock()
    totals = [0, 0, 0]

    async def worker() -> None:
        while (i := await _next_job(jobs, lock)) is not None:
            for attempt in range(1, retry + 1):
                try:
                    prompt, bg, skipped = await fetch_group(
                        g, prompt_dir, bg_root, per_prompt
                    )
                except Exception as e:
                    if attempt == retry:
                        print(f'[{i}/{count}] failed ({retry} tries): {e}')
                        break
                    await asyncio.sleep(delay * attempt)
                else:
                    async with lock:
                        totals[0] += prompt
                        totals[1] += bg
                        totals[2] += skipped
                    note = 'bg skip (分组已满)' if skipped else f'bg +{bg}'
                    print(f'[{i}/{count}] prompt +{prompt} {note}')
                    break

    await asyncio.gather(*(worker() for _ in range(min(concurrency, count))))
    print(f'done: prompt +{totals[0]} bg +{totals[1]} (跳过 {totals[2]}) -> {out_dir}')


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
        '--per-prompt',
        type=int,
        default=DEFAULT_PER_PROMPT,
        help=f'每个 prompt 最多保留多少张背景图, 0 表示不限 (默认 {DEFAULT_PER_PROMPT})',
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
            per_prompt=args.per_prompt,
        )
    )


if __name__ == '__main__':
    main()
