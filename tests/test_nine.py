"""nine 扩展的测试，按标记分三组：

    uv run pytest tests/test_nine.py -m draw        # 绘图 debug，线上拉一张
    uv run pytest tests/test_nine.py -m accuracy    # 线上首猜通过率
    uv run pytest tests/test_nine.py -m perf        # 性能基准 (pytest-benchmark)

``draw`` / ``accuracy`` 都要联网，模型首次运行从 HuggingFace 拉（之后走本地缓存）；
``accuracy`` 会真提交答案，慢且消耗挑战配额；
``perf`` 离线运行，使用本地缓存或合成样本评测推理性能。
"""

from __future__ import annotations

import hashlib
import os
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from wulu_geetest_bypass import Geetest

pytest.importorskip('wulu_geetest_bypass_nine')

from wulu_geetest_bypass_nine import score_nine, solve_nine


def _draw(
    imgs: bytes,
    ques: list[bytes],
    order: list[int],
    logits: list[float],
    nine_nums: int,
    out: Path,
) -> None:
    grid = Image.open(BytesIO(imgs)).convert('RGB')
    w, h = grid.size
    cw, ch = w // 3, h // 3
    bar = 60

    canvas = Image.new('RGB', (w, h + bar), (245, 247, 250))
    canvas.paste(grid, (0, bar))
    if ques:
        q_img = Image.open(BytesIO(ques[0])).resize((50, 50))
        mask = q_img.split()[3] if q_img.mode == 'RGBA' else None
        canvas.paste(q_img, (10, 5), mask=mask)

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=15)
    picked = {cell: rank + 1 for rank, cell in enumerate(order[:nine_nums])}

    for cell in range(9):
        x, y = (cell % 3) * cw, bar + (cell // 3) * ch
        hit = cell in picked
        color = (0, 220, 80) if hit else (240, 60, 60)
        draw.rectangle(
            (x, y, x + cw - 1, y + ch - 1), outline=color, width=3 if hit else 1
        )
        draw.text((x + 4, y + 4), f'{logits[cell]:+.2f}', fill=color, font=font)
        if hit:
            draw.text(
                (x + cw - 16, y + ch - 20), str(picked[cell]), fill=color, font=font
            )

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


@pytest.mark.draw
@pytest.mark.asyncio
async def test_nine_draw(cid, out_dir):
    g = Geetest(captcha_id=cid, risk_type='nine')
    data = await g.load()
    imgs, *ques = await g._load_resources(data['imgs'], *data['ques'])
    nine_nums = data['nine_nums']
    prompt_hash = hashlib.md5(ques[0]).hexdigest()

    order, logits = score_nine(imgs, ques)
    cells = solve_nine(imgs, ques, nine_nums)

    out = out_dir / 'nine.png'
    _draw(imgs, ques, order, logits, nine_nums, out)

    assert len(cells) == nine_nums, f'expected {nine_nums} cells, got {cells}'
    assert len({tuple(c) for c in cells}) == nine_nums, f'duplicate cells: {cells}'
    assert all(1 <= r <= 3 and 1 <= c <= 3 for r, c in cells), f'not 1-based: {cells}'

    print(f'\nnine(draw): prompt={prompt_hash} (nums={nine_nums})')
    print(f'nine(draw): cells={cells}')
    print('nine(draw): logits=' + ' '.join(f'{v:+.2f}' for v in logits))
    print(f'nine(draw): out -> {out}')


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_nine_pass_rate(pass_rate):
    """线上首猜通过率：完整链路验证 (load -> solver -> track -> verify)。"""
    await pass_rate(
        'nine',
        0.5,
        lambda d: solve_nine(d['imgs'], d['ques'], d['nine_nums']),
        captcha_id=os.environ.get('WULU_NINE_CID'),
    )


@pytest.fixture(scope='session')
def perf_sample() -> tuple[bytes, list[bytes], int]:
    """准备性能测试样本 (grid_bytes, ques, nine_nums) 并完成模型预热。"""
    try:
        from wulu_geetest_bypass_nine.solver import _session

        info = _session()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'九宫格模型不可用: {e}')

    # 优先使用真实样本图，若无则使用标准尺寸 (260x160) 的合成图
    sample_dir = (
        Path(__file__).resolve().parents[1] / 'resources' / 'collect' / 'nine' / 'bg'
    )
    real_bgs = list(sample_dir.glob('*.png')) if sample_dir.is_dir() else []
    if real_bgs:
        grid_bytes = real_bgs[0].read_bytes()
    else:
        grid_img = Image.new('RGB', (260, 160), (140, 160, 180))
        buf = BytesIO()
        grid_img.save(buf, format='PNG')
        grid_bytes = buf.getvalue()

    # 构造能够命中已知类别的 prompt，确保前向推理打通
    target_hash = next(iter(info.class_map.keys()))
    dummy_prompt = b'perf_dummy_prompt_bytes'
    info.class_map[hashlib.md5(dummy_prompt).hexdigest()] = info.class_map[target_hash]

    # 预热推理会话
    for _ in range(5):
        solve_nine(grid_bytes, [dummy_prompt], 3)

    return grid_bytes, [dummy_prompt], 3


@pytest.mark.perf
def test_perf_solve_nine(benchmark, perf_sample):
    """端到端 solve_nine 基准测试（整图 9 格批次裁切 + ONNX 推理 + 排序）"""
    grid_bytes, ques, nine_nums = perf_sample
    benchmark.extra_info['type'] = 'nine'
    res = benchmark(lambda: solve_nine(grid_bytes, ques, nine_nums))
    assert len(res) == nine_nums


@pytest.mark.perf
def test_perf_prep(benchmark, perf_sample):
    """前处理性能：9 格黑边检测与裁切、双线性缩放、归一化成批张量"""
    from wulu_geetest_bypass_nine.solver import _prep_batch, _session

    grid_bytes, _, _ = perf_sample
    info = _session()
    img = Image.open(BytesIO(grid_bytes)).convert('RGB')
    benchmark(lambda: _prep_batch(img, size=info.input_size))


@pytest.mark.perf
def test_perf_profile(perf_sample):
    """单趟延迟分布剖析：统计各阶段耗时（前处理、网络推理、端到端中位数与 p95）"""
    from wulu_geetest_bypass_nine.solver import _prep_batch, _session

    grid_bytes, ques, nine_nums = perf_sample
    info = _session()
    grid = Image.open(BytesIO(grid_bytes)).convert('RGB')

    prep_ms, infer_ms, total_ms = [], [], []
    for _ in range(50):
        t0 = time.perf_counter()
        tensors = _prep_batch(grid, size=info.input_size)
        t1 = time.perf_counter()
        info.session.run([info.output_name], {info.input_name: tensors})
        t2 = time.perf_counter()
        solve_nine(grid_bytes, ques, nine_nums)
        t3 = time.perf_counter()

        prep_ms.append((t1 - t0) * 1000)
        infer_ms.append((t2 - t1) * 1000)
        total_ms.append((t3 - t2 + (t2 - t0)) * 1000)

    p50 = float(np.median(total_ms))
    p95 = float(np.percentile(total_ms, 95))
    print(
        f'\nnine(perf): 前处理={np.median(prep_ms):.2f}ms | '
        f'模型推理={np.median(infer_ms):.2f}ms | '
        f'端到端: 中位={p50:.2f}ms p95={p95:.2f}ms (n=50)'
    )
    assert p50 < 50, f'中位延迟 {p50:.1f}ms 超过 50ms 阈值'
