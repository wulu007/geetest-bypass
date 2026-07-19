import base64
import os

import cv2
import numpy as np
import pytest
import resvg_py

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.solver.svg import _grid_svgs, _rgba_to_gray, match

out_dir = 'resources/match_demo'
os.makedirs(out_dir, exist_ok=True)


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
            f'{scores[i + 1]:.3f}',
            (x, y + h + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            255,
            1,
        )

    return canvas


def _edges(grids):
    return [cv2.Canny(_rgba_to_gray(resvg_py.svg_to_bytes(g)), 50, 150) for g in grids]


@pytest.mark.asyncio
async def test_svg_seed():
    g = Geetest(captcha_id='54088bb07d2df3c46b79f80300b0abbe', risk_type='svg_seed')
    data = await g.load()
    svg = data['question_path']
    hint_raw = base64.b64decode(data['answer_path'])
    hint_edge = cv2.Canny(_rgba_to_gray(hint_raw), 50, 150)
    grids = _grid_svgs(svg)
    imgs = _edges(grids)
    results = match(svg, data['answer_path'])
    scores = {r['grid']: r['score'] for r in results}
    best_i = max(scores, key=scores.get)

    canvas = _composite(imgs, scores, best_i, hint_edge, n_cols=7)
    cv2.imwrite(os.path.join(out_dir, 'seed_grids.png'), canvas)
    print(f'seed: best=grid {best_i} score={scores[best_i]:.3f}')


@pytest.mark.asyncio
async def test_svg_icon():
    g = Geetest(captcha_id='54088bb07d2df3c46b79f80300b0abbe', risk_type='svg_icon')
    data = await g.load()
    svg = (await g._load_img(data['question_path'])).decode()
    hint_raw = await g._load_img(data['answer_path'])

    results = match(svg, hint_raw)
    scores = {r['grid']: r['score'] for r in results}
    best_i = max(scores, key=scores.get)

    hint_edge = cv2.Canny(_rgba_to_gray(hint_raw), 50, 150)
    grids = _grid_svgs(svg)
    imgs = _edges(grids)

    canvas = _composite(imgs, scores, best_i, hint_edge, n_cols=4)
    cv2.imwrite(os.path.join(out_dir, 'icon_grids.png'), canvas)
    print(f'icon: best=grid {best_i} score={scores[best_i]:.3f}')
