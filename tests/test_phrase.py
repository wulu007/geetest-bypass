"""phrase 扩展的测试，按标记分成三组：

    uv run pytest tests/test_phrase.py -m draw        # 绘图 debug
    uv run pytest tests/test_phrase.py -m accuracy    # 线上通过率
    uv run pytest tests/test_phrase.py -m perf        # 性能
    uv run pytest tests/test_phrase.py -m 'not accuracy'   # 跳过吃配额的那组

``draw`` / ``accuracy`` 需要联网（拉题目），并且首次运行要从 HuggingFace 拉模型和字典；
``perf`` 尽量离线（模型/字典走本地缓存，拿不到就 skip）。

性能用 pytest-benchmark：``test_perf_profile`` 看跨图分布，另外三个 ``test_perf_*`` 是
多轮基准（自动校准轮数、统计离群值）。存/比基线::

    uv run pytest tests/test_phrase.py -m perf --benchmark-autosave
    uv run pytest tests/test_phrase.py -m perf --benchmark-compare --benchmark-compare-fail=median:15%
    uv run pytest tests/test_phrase.py -m perf --benchmark-disable   # 跳过基准，只跑分布那趟

可调环境变量：
    WULU_PHRASE_PASS_SAMPLES  通过率测多少张（默认 50）
    WULU_PHRASE_MIN_RATE      通过率下限（默认 0.9）
    WULU_PHRASE_PERF_IMAGES   性能跑多少张语料（默认 40）
"""

import asyncio
import itertools
import os
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass._exceptions import RateLimitError

pytest.importorskip('wulu_geetest_bypass_phrase')

from wulu_geetest_bypass_phrase.solver import _dict, _locate, _order, _recognize

_ROOT = Path(__file__).resolve().parents[1]
_CORPUS = _ROOT / 'resources' / 'collect' / 'phrase'


def _draw(img: np.ndarray, boxes, chars, order, load_font) -> np.ndarray:
    """绿框标出每个字，"序号.字" 写在框上方；框太靠顶就写到框下方，避免出画。

    ``load_font`` 是 conftest 的 ``cjk_font`` fixture 给的加载函数。
    """
    from PIL import Image, ImageDraw

    tile = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    width, height = tile.size
    canvas = ImageDraw.Draw(tile)
    size = max(12, round(float(np.median([h for *_, h in boxes])) * 0.30))
    font, cjk_ok = load_font(size)
    line = round(size * 1.25)

    # 第 k 次点击的是 boxes[order[k]]，按 order 反查每个框的点第几次
    rank = {box: k + 1 for k, box in enumerate(order)}
    for i, (x, y, w, h) in enumerate(boxes):
        canvas.rectangle((x, y, x + w, y + h), outline=(0, 255, 0), width=2)
        label = f'{rank[i]}.{chars[i]}' if cjk_ok else str(rank[i])
        text_w = canvas.textlength(label, font=font)
        above = y - line
        below = y + h + 2
        top = above if above >= 0 else min(below, height - line)
        canvas.text(
            (int(min(max(0, x), max(0, width - text_w))), int(min(top, height - line))),
            label,
            font=font,
            fill=(0, 255, 0),
            stroke_width=2,  # 描边：标签常压在别的框/字上，不然看不清
            stroke_fill=(0, 0, 0),
        )
    return cv2.cvtColor(np.asarray(tile), cv2.COLOR_RGB2BGR)


def _p95(ms: list[float]) -> float:
    return float(np.percentile(ms, 95)) if ms else 0.0


def _stats(ms: list[float]) -> str:
    arr = np.asarray(ms)
    return (
        f'中位 {np.median(arr):6.1f}ms  p95 {np.percentile(arr, 95):6.1f}ms  '
        f'最大 {arr.max():6.1f}ms'
    )


@pytest.mark.draw
@pytest.mark.asyncio
async def test_phrase_draw(cid, out_dir, cjk_font):
    """拉一张挑战，定位 + 识别 + 语序还原，画出点击顺序。"""
    g = Geetest(captcha_id=cid, risk_type='phrase')
    data = await g.load()
    img = cv2.imdecode(
        np.frombuffer(await g._load_resource(data['imgs']), np.uint8), cv2.IMREAD_COLOR
    )
    assert img is not None, 'failed to decode the challenge image'

    boxes = _locate(img)
    chars = _recognize(img, boxes)
    name = str(data['imgs']).rsplit('/', 1)[-1]
    print(f'phrase(draw): {name[:8]} boxes={len(boxes)} chars={"".join(chars)}')
    assert len(boxes) == 4, f'expected 4 boxes, got {len(boxes)}'
    assert all(chars), f'recognition incomplete: {chars}'

    order = _order(chars)
    print(
        f'phrase(draw): 点击顺序 {"".join(chars[i] for i in order)}（框下标 {order}）'
    )
    assert sorted(order) == list(range(4)), f'not a permutation: {order}'

    load_font, path = cjk_font
    out = out_dir / 'phrase.png'
    cv2.imwrite(str(out), _draw(img, boxes, chars, order, load_font))
    print(f'phrase(draw): 字体 {path or "无（本机没有中文字体，只画序号）"}')
    print(f'phrase(draw): {out}')


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_phrase_pass_rate(cid):
    """黑盒跑生产链路（load -> verify，语序由注册的 solver 决定），统计首猜通过率。

    走的是 ``Geetest.auto_solve``，所以定位/识别/语序还原/点击换算/轨迹全都覆盖。
    """
    total = int(os.environ.get('WULU_PHRASE_PASS_SAMPLES', '50'))
    floor = float(os.environ.get('WULU_PHRASE_MIN_RATE', '0.9'))
    g = Geetest(captcha_id=cid, risk_type='phrase')
    hit = attempted = 0
    while attempted < total:
        data = await g.load()
        try:
            resp = await g.verify(data)
        except RateLimitError:
            print('phrase(accuracy): 限流，退避 5s')
            await asyncio.sleep(5.0)
            continue
        await asyncio.sleep(0.5)
        result = resp['data']['result']
        attempted += 1
        hit += result == 'success'
        print(f'phrase(accuracy): {attempted:>3d}/{total} {result}')
    rate = hit / attempted
    print(f'phrase(accuracy): 首猜通过 {hit}/{attempted} = {rate:.1%}')
    assert rate >= floor, f'通过率 {rate:.1%} 低于下限 {floor:.0%}'


@pytest.fixture(scope='session')
def perf_corpus():
    """本地语料子集 + 预热，返回 ``(imgs, boxes_all, chars_all, table)``。

    预热省不得：首次调用要下拉模型/字典、建 onnx session，不预热这段开销会被算进第一次测量。
    """
    cap = int(os.environ.get('WULU_PHRASE_PERF_IMAGES', '40'))
    files = sorted(_CORPUS.glob('*.jpg'))[:cap]
    if not files:
        pytest.skip(f'no corpus under {_CORPUS}')
    imgs = [img for f in files if (img := cv2.imread(str(f))) is not None]
    try:
        table = _dict()[0]
        boxes_all = [_locate(img) for img in imgs]
        chars_all = [_recognize(img, b) for img, b in zip(imgs, boxes_all, strict=True)]
        _order(list('澡洗束结'))  # 字典肯定没有的字集合：把模型那条路也预热
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'模型或字典不可用: {type(e).__name__} {e}')
    print(f'phrase(perf): 语料 {len(imgs)} 张（WULU_PHRASE_PERF_IMAGES 可调）')
    return imgs, boxes_all, chars_all, table


@pytest.mark.perf
def test_perf_locate(benchmark, perf_corpus):
    """定位：一次调用一张图，轮转整批语料（报告里的数字就是单张耗时）。"""
    images = itertools.cycle(perf_corpus[0])
    benchmark(lambda: _locate(next(images)))


@pytest.mark.perf
def test_perf_recognize(benchmark, perf_corpus):
    """识别：一次调用一张图（框用 fixture 里算好的，只测识别本身）。"""
    crops = itertools.cycle(perf_corpus[0]), itertools.cycle(perf_corpus[1])
    benchmark(lambda: _recognize(next(crops[0]), next(crops[1])))


@pytest.mark.perf
def test_perf_order_dict(benchmark, perf_corpus):
    """语序还原（字典命中）：只查表，不该带上模型开销。"""
    _, _, chars_all, table = perf_corpus
    hits = [
        c for c in chars_all if len(c) == 4 and all(c) and ''.join(sorted(c)) in table
    ]
    if not hits:
        pytest.skip('语料里没有命中字典的字集合')
    cases = itertools.cycle(hits)
    benchmark(lambda: _order(next(cases)))
    print(f'phrase(perf): 字典命中样本 {len(hits)} 个（轮转）')


@pytest.mark.perf
def test_perf_order_model(benchmark, perf_corpus):
    """语序还原（走 order.onnx）：字典没命中的字集合 + 两个合成用例。"""
    _, _, chars_all, table = perf_corpus
    miss = [
        c
        for c in chars_all
        if len(c) == 4 and all(c) and ''.join(sorted(c)) not in table
    ]
    cases = itertools.cycle(miss + [list('澡洗束结'), list('擦桌擦子')])
    benchmark(lambda: _order(next(cases)))
    print(f'phrase(perf): 走模型样本 {len(miss)} + 2 合成（轮转）')


@pytest.mark.perf
def test_perf_profile(perf_corpus):
    """单趟分布：看的是**跨图差异**（各阶段中位与 p95），不追求重复稳定性。"""
    imgs, boxes_all, chars_all, table = perf_corpus
    stages: dict[str, list[float]] = {
        '定位': [],
        '识别': [],
        '还原(字典)': [],
        '还原(模型)': [],
    }
    total: list[float] = []
    for img, boxes, chars in zip(imgs, boxes_all, chars_all, strict=True):
        t0 = time.perf_counter()
        _locate(img)
        t1 = time.perf_counter()
        _recognize(img, boxes)
        t2 = time.perf_counter()
        stages['定位'].append((t1 - t0) * 1000)
        stages['识别'].append((t2 - t1) * 1000)
        if len(boxes) == 4 and all(chars):
            from_dict = len(set(chars)) == 4 and ''.join(sorted(chars)) in table
            _order(chars)
            stages['还原(字典)' if from_dict else '还原(模型)'].append(
                (time.perf_counter() - t2) * 1000
            )
        total.append((time.perf_counter() - t0) * 1000)

    for name, ms in stages.items():
        if ms:
            print(f'phrase(perf): {name:<10s} n={len(ms):>3d}  {_stats(ms)}')
    print(f'phrase(perf): 整条链路   n={len(total):>3d}  {_stats(total)}')
    assert _p95(total) < 1000, f'整条链路 p95 {_p95(total):.0f}ms 超过 1s'
