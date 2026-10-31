import base64
import itertools
from io import BytesIO

import cv2
import numpy as np
import pytest
import resvg_py
from PIL import Image

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.solver.svg import (
    _grid_svgs,
    _hint_to_edge,
    _rgba_to_gray,
    frame_times,
    match,
)


def _dump_svg(svg: str, out) -> None:
    out.write_text(svg, encoding='utf-8')


def _to_bgr(png: bytes) -> np.ndarray:
    """SVG/PNG → BGR，透明部分垫白底。"""
    img = Image.open(BytesIO(png))
    bg = Image.new('RGB', img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
    return cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)


def _locate(grid_svg: str, hint_edge: np.ndarray) -> tuple[int, int, int, int]:
    """最佳格子里 hint 边缘的命中位置（x, y, w, h），用来在彩图上画框。"""
    edge = cv2.Canny(_rgba_to_gray(resvg_py.svg_to_bytes(grid_svg)), 50, 150)
    _, _, _, loc = cv2.minMaxLoc(
        cv2.matchTemplate(edge, hint_edge, cv2.TM_CCORR_NORMED)
    )
    return loc[0], loc[1], hint_edge.shape[1], hint_edge.shape[0]


_RANK_COLORS = ((80, 180, 80), (0, 170, 255), (200, 130, 40))  # 冠军 / 亚军 / 季军


def _fit(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """把 hint 缩放到格子内（保持长宽比），否则小图看不清。"""
    h, w = size
    scale = min(h / img.shape[0], w / img.shape[1])
    if scale >= 0.95:
        return img
    return cv2.resize(
        img,
        (max(1, int(img.shape[1] * scale)), max(1, int(img.shape[0] * scale))),
        interpolation=cv2.INTER_CUBIC,
    )


def _composite(imgs, scores, best_i, hint, box, n_cols):
    h, w = imgs[0].shape[:2]
    gap, cap = 8, 22
    n_rows = (len(imgs) + n_cols - 1) // n_cols + 1
    cw = gap + n_cols * (w + gap)
    ch = gap + n_rows * (h + gap + cap)
    canvas = np.full((ch, cw, 3), 250, dtype=np.uint8)
    rank = {g: i for i, g in enumerate(sorted(scores, key=scores.get, reverse=True))}

    def paste(img, row, col):
        y = gap + row * (h + gap + cap)
        x = gap + col * (w + gap)
        canvas[y : y + h, x : x + w] = img
        return x, y

    def label(text, x, y, color):
        cv2.putText(
            canvas,
            text,
            (x, y + h + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    hint = _fit(hint, (h, w))
    hint_pad = np.full((h, w, 3), 250, dtype=np.uint8)
    hh, hw = hint.shape[:2]
    hint_pad[(h - hh) // 2 : (h - hh) // 2 + hh, (w - hw) // 2 : (w - hw) // 2 + hw] = (
        hint
    )
    x, y = paste(hint_pad, 0, 0)
    label('HINT', x, y, (200, 120, 0))

    for i, img in enumerate(imgs):
        x, y = paste(img, i // n_cols + 1, i % n_cols)
        color = _RANK_COLORS[rank[i + 1]] if rank[i + 1] < 3 else (205, 205, 205)
        cv2.rectangle(
            canvas,
            (x, y),
            (x + w - 1, y + h - 1),
            color,
            3 if (i + 1) == best_i else 1,
        )
        if (i + 1) == best_i:
            bx, by, bw, bh = box
            cv2.rectangle(
                canvas, (x + bx, y + by), (x + bx + bw, y + by + bh), (40, 40, 220), 2
            )
        label(f'{i + 1}: {scores[i + 1]}', x, y, color)

    return canvas


async def _load_svg_resources(cid, risk_type):
    g = Geetest(captcha_id=cid, risk_type=risk_type)
    data = await g.load()
    q, a = data['question_path'], data['answer_path']
    if risk_type == 'svg_seed':
        svg, hint = q, base64.b64decode(a)
    else:
        svg = (await g._load_resource(q)).decode()
        hint = await g._load_resource(a)
    return svg, hint


@pytest.mark.asyncio
@pytest.mark.parametrize('risk_type', ['svg_seed', 'svg_icon'])
async def test_frame_times(cid, risk_type):
    svg, _ = await _load_svg_resources(cid, risk_type)
    frames = frame_times(svg)
    assert len(frames) == 3
    for (s1, e1), (s2, e2) in itertools.pairwise(frames):
        assert s2 - e1 <= 1
        assert s2 > s1
        assert e2 > e1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('risk_type', 'n_cols'),
    [('svg_seed', 7), ('svg_icon', 4)],
)
async def test_svg_seed_solve(cid, svg_out_dir, risk_type, n_cols):
    svg, hint = await _load_svg_resources(cid, risk_type)
    hint_edge = _hint_to_edge(hint)
    _dump_svg(svg, svg_out_dir / f'{risk_type}.svg')
    grids = _grid_svgs(svg)
    imgs = [_to_bgr(resvg_py.svg_to_bytes(g)) for g in grids]
    results = match(svg, hint)
    scores = {r['grid']: r['score'] for r in results}
    best_i = max(scores, key=lambda k: scores[k])

    box = _locate(grids[best_i - 1], hint_edge)
    canvas = _composite(imgs, scores, best_i, _to_bgr(hint), box, n_cols=n_cols)
    out = svg_out_dir / f'{risk_type}.png'
    cv2.imwrite(out, canvas)
    print(f'{risk_type}: best=grid {best_i} score={scores[best_i]} {out}')


@pytest.mark.accuracy
@pytest.mark.asyncio
@pytest.mark.parametrize('risk_type', ['svg_seed', 'svg_icon'])
async def test_svg_pass_rate(pass_rate, risk_type):
    from wulu_geetest_bypass.solver.svg import solve_svg

    await pass_rate(
        risk_type, 0.8, lambda d: solve_svg(d['question_path'], d['answer_path'])
    )
