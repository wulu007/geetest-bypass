import base64
import itertools

import cv2
import numpy as np
import pytest
import resvg_py

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.solver.svg import _grid_svgs, _rgba_to_gray, frame_times, match


def _dump_svg(svg: str, out) -> None:
    out.write_text(svg, encoding='utf-8')


def _composite(imgs, scores, best_i, hint_edge, n_cols):
    h, w = imgs[0].shape
    gap = 6
    n_rows = (len(imgs) + n_cols - 1) // n_cols + 1
    cw = gap + n_cols * (w + gap)
    ch = gap + n_rows * (h + gap + 20)
    canvas = np.full((ch, cw), 0, dtype=np.uint8)

    def put(img, row, col, text=''):
        y = gap + row * (h + gap + 20)
        x = gap + col * (w + gap)
        canvas[y : y + h, x : x + w] = img
        if text:
            cv2.putText(
                canvas, text, (x, y + h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 255, 1
            )

    hint_pad = np.full((h, w), 0, dtype=np.uint8)
    hh, hw = min(hint_edge.shape[0], h), min(hint_edge.shape[1], w)
    hy, hx = (h - hh) // 2, (w - hw) // 2
    hint_pad[hy : hy + hh, hx : hx + hw] = hint_edge[:hh, :hw]
    put(hint_pad, 0, 1, 'HINT')

    for i, img in enumerate(imgs):
        row = i // n_cols + 1
        col = i % n_cols
        y = gap + row * (h + gap + 20)
        x = gap + col * (w + gap)
        canvas[y : y + h, x : x + w] = img
        if (i + 1) == best_i:
            cv2.rectangle(canvas, (x, y), (x + w - 1, y + h - 1), 255, 2)
        cv2.putText(
            canvas,
            f'{scores[i + 1]}',
            (x, y + h + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            255,
            1,
        )

    return canvas


def _edges(grids):
    return [cv2.Canny(_rgba_to_gray(resvg_py.svg_to_bytes(g)), 50, 150) for g in grids]


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
    hint_edge = cv2.Canny(_rgba_to_gray(hint), 50, 150)
    _dump_svg(svg, svg_out_dir / f'{risk_type}.svg')
    grids = _grid_svgs(svg)
    imgs = _edges(grids)
    results = match(svg, hint)
    scores = {r['grid']: r['score'] for r in results}
    best_i = max(scores, key=lambda k: scores[k])

    canvas = _composite(imgs, scores, best_i, hint_edge, n_cols=n_cols)
    out = svg_out_dir / f'{risk_type}.png'
    cv2.imwrite(out, canvas)
    print(f'{risk_type}: best=grid {best_i} score={scores[best_i]} {out}')
