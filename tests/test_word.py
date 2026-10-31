"""word 扩展的测试，按标记分三组：

    uv run pytest tests/test_word.py -m draw        # 绘图 debug，线上拉一张并绘制候选框与点击顺序
    uv run pytest tests/test_word.py -m accuracy    # 线上通过率评测 (50 题)
    uv run pytest tests/test_word.py -m perf        # 性能耗时基准
    uv run pytest tests/test_word.py                # 默认离线测试

``draw`` / ``accuracy`` 需要联网（拉取题目与校验）；
``perf`` 与默认测试离线运行。
"""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.utils import format_userresponse

pytest.importorskip('wulu_geetest_bypass_word')

from wulu_geetest_bypass_word import detect_candidates, solve_word

RESOURCES_DIR = (
    Path(__file__).resolve().parents[1] / 'resources' / 'solver_debug' / 'word'
)
THUMB = 48


def _load_sample() -> tuple[bytes, list[bytes]]:
    imgs_path = RESOURCES_DIR / 'imgs.png'
    ques_paths = [RESOURCES_DIR / f'ques_{i}.png' for i in range(3)]
    if imgs_path.is_file() and all(p.is_file() for p in ques_paths):
        return imgs_path.read_bytes(), [p.read_bytes() for p in ques_paths]

    # 兜底：合成最小有效测试图像（无须外部文件即可通过离线测试）
    bg = Image.new('RGB', (300, 200), (240, 240, 240))
    buf = BytesIO()
    bg.save(buf, format='PNG')
    imgs = buf.getvalue()

    ques: list[bytes] = []
    for _ in range(3):
        q = Image.new('RGBA', (40, 40), (200, 100, 100, 255))
        b = BytesIO()
        q.save(b, format='PNG')
        ques.append(b.getvalue())

    return imgs, ques


def _badge(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    cx: int,
    cy: int,
    text: str,
    fill: tuple[int, int, int] = (220, 40, 40),
) -> None:
    """带白边的小圆徽标，压在图上也不会被笔画吃掉。"""
    r = 9
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=(255, 255, 255))
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (cx - (right - left) / 2, cy - (bottom - top) / 2 - top),
        text,
        fill=(255, 255, 255),
        font=font,
    )


def _draw(
    imgs: bytes,
    ques: list[bytes],
    clicks: list[tuple[float, float]],
    boxes: Sequence[Sequence[int]],
    out: Path,
) -> None:
    bg = Image.open(BytesIO(imgs)).convert('RGB')
    w, h = bg.size
    bar_h = THUMB + 12

    canvas = Image.new('RGB', (w, h + bar_h), (245, 247, 250))
    canvas.paste(bg, (0, bar_h))

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=13)

    # 题图排一行，序号压在缩略图右下角
    x = 10
    for idx, blob in enumerate(ques, start=1):
        icon = Image.open(BytesIO(blob)).convert('RGBA')
        icon.thumbnail((THUMB, THUMB), Image.Resampling.LANCZOS)
        tile = Image.new('RGBA', (THUMB, THUMB), (0, 0, 0, 0))
        tile.paste(icon, ((THUMB - icon.width) // 2, (THUMB - icon.height) // 2))
        canvas.paste(tile, (x, 6), tile.split()[3])
        _badge(draw, font, x + THUMB - 2, 6 + THUMB - 2, str(idx))
        x += THUMB + 8

    # 候选框
    for bx, by, bw, bh in boxes:
        draw.rectangle(
            [bx, bar_h + by, bx + bw, bar_h + by + bh], outline=(70, 180, 245), width=2
        )

    # 点击顺序只用框角上的序号标注，图上不画任何盖住字形的东西
    for idx, (nx, ny) in enumerate(clicks, start=1):
        cy = round(ny * h)
        hit = next(
            (
                b
                for b in boxes
                if b[0] <= nx * w <= b[0] + b[2] and b[1] <= cy <= b[1] + b[3]
            ),
            None,
        )
        ax, ay = (hit[0], bar_h + hit[1]) if hit else (round(nx * w), bar_h + cy)
        _badge(
            draw,
            font,
            max(10, min(ax, w - 10)),
            max(bar_h + 10, ay),
            str(idx),
            fill=(30, 30, 30),
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def test_solve_word_offline():
    imgs, ques = _load_sample()
    clicks = solve_word(imgs, ques)

    assert len(clicks) == len(ques)
    for x, y in clicks:
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0

    wire = format_userresponse(clicks)
    assert len(wire) == len(ques)
    for coord in wire:
        assert len(coord) == 2
        assert 0 <= coord[0] <= 10000
        assert 0 <= coord[1] <= 10000


def test_word_auto_solve():
    imgs, ques = _load_sample()
    payload = {
        'captcha_id': 'test_id',
        'captcha_type': 'word',
        'lot_number': 'lot_123',
        'pow_detail': {},
        'guard': False,
        'captcha_mode': 'adaptive',
        'static_path': '/v4/static/v1.9.8-0d53fd',
        'pt': 1,
        'imgs': imgs,
        'ques': ques,
    }

    ans = Geetest.auto_solve(payload)  # type: ignore[arg-type]
    assert 'userresponse' in ans
    assert 'track' in ans
    assert 'passtime' in ans

    assert len(ans['userresponse']) == len(ques)
    assert ans['passtime'] > 0


@pytest.mark.draw
@pytest.mark.asyncio
async def test_word_draw(cid, out_dir):
    """从线上拉取真实 Word 挑战，执行检测与匹配，并绘制带编号的结果图。"""
    g = Geetest(captcha_id=cid, risk_type='word')
    data = await g.load()
    imgs, *ques = await g._load_resources(data['imgs'], *data['ques'])

    # 与 solve_word 用同一批框（它自己取分数最高的 5 个），否则标注图上会多画背景纹理框
    boxes = detect_candidates(imgs, limit=5)
    clicks = solve_word(imgs, ques)

    out = out_dir / 'word.png'
    _draw(imgs, ques, clicks, boxes, out)

    assert len(clicks) == len(ques)
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in clicks)

    print(f'\nword(draw): prompt_count={len(ques)} detections={len(boxes)}')
    print(f'word(draw): clicks={clicks}')
    print(f'word(draw): out -> {out}')


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_word_pass_rate(pass_rate):
    """黑盒跑生产链路（load -> auto_solve -> verify），统计首猜通过率并自动捕获失败用例。"""

    def draw_failure(data, case):
        imgs, ques = data['imgs'], data['ques']
        clicks = solve_word(imgs, ques)
        boxes = detect_candidates(imgs, limit=5)
        _draw(imgs, ques, clicks, boxes, case / 'annotated.png')

    await pass_rate(
        'word',
        0.9,
        lambda d: solve_word(d['imgs'], d['ques']),
        on_fail=draw_failure,
    )


@pytest.mark.perf
def test_word_perf(benchmark):
    """测试单题在 CPU 上的端到端推理耗时（基于 pytest-benchmark）。"""
    imgs, ques = _load_sample()
    benchmark.extra_info['type'] = 'word'
    res = benchmark(lambda: solve_word(imgs, ques))
    assert len(res) == len(ques)
