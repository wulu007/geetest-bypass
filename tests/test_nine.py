from __future__ import annotations

from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from wulu_geetest_bypass_nine import (
    compute_cross_modal_similarity,
    get_global_feature_extractor,
    preprocess_to_edge_map,
    score_nine,
)

from wulu_geetest_bypass import Geetest


def _draw_result(
    imgs: np.ndarray,
    scores: list[float],
    order: list[int],
    n_click: int,
    out: Path,
    ques_imgs=None,
) -> None:
    h, w = imgs.shape[:2]
    cw, ch = w // 3, h // 3

    if ques_imgs:
        qw = min(ques_imgs[0].shape[1], cw)
        qh = min(ques_imgs[0].shape[0], ch)
        panel_h = qh + 8
        canvas = np.full((h + panel_h, w, 3), 255, dtype=np.uint8)
        canvas[panel_h:] = imgs
        for i, q in enumerate(ques_imgs):
            q = cv2.resize(q, (qw, qh))
            x = 8 + i * (qw + 8)
            canvas[:qh, x : x + qw] = q
        off = panel_h
    else:
        canvas = imgs.copy()
        off = 0

    selected = set(order[:n_click])
    for idx, score in enumerate(scores):
        row, col = divmod(idx, 3)
        x, y = col * cw, row * ch + off
        color = (0, 0, 255) if idx in selected else (0, 0, 0)
        label = f'{score:.3f}'
        cv2.rectangle(canvas, (x, y), (x + cw - 1, y + ch - 1), color, 3)
        cv2.putText(
            canvas,
            label,
            (x + 4, y + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
        )
    for i, idx in enumerate(order[:n_click]):
        row, col = divmod(idx, 3)
        x, y = col * cw, row * ch + off
        cv2.putText(
            canvas,
            str(i + 1),
            (x + cw - 20, y + ch - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
    cv2.imwrite(str(out), canvas)


async def _load_nine_resources(cid):
    g = Geetest(captcha_id=cid, risk_type='nine')
    data = await g.load()
    imgs = await g._load_resource(data['imgs'])
    ques = [await g._load_resource(url) for url in data['ques']]
    return g, data, imgs, ques


def _split_cells(img: Image.Image) -> list[Image.Image]:
    w, h = img.size
    cw, ch = w // 3, h // 3
    return [
        img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
        for r in range(3)
        for c in range(3)
    ]


def _icon_rgb(data: bytes) -> Image.Image:
    """Crop RGBA silhouette to its opaque bbox and composite on white."""
    icon = Image.open(BytesIO(data)).convert('RGBA')
    alpha = np.asarray(icon)[:, :, 3] > 100
    ys, xs = np.where(alpha)
    if len(ys):
        icon = icon.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    bg = Image.new('RGBA', icon.size, (255, 255, 255, 255))
    bg.alpha_composite(icon)
    return bg.convert('RGB')


@pytest.mark.asyncio
async def test_nine_solver_draw(cid, out_dir):
    g, data, imgs, ques = await _load_nine_resources(cid)
    nine_nums = data['nine_nums']
    grid = cv2.imdecode(np.frombuffer(imgs, np.uint8), cv2.IMREAD_COLOR)

    assert grid is not None, 'Failed to load nine grid image'
    debug_dir = out_dir / 'solver_debug' / 'nine'
    debug_dir.mkdir(parents=True, exist_ok=True)
    for i, q in enumerate(ques):
        (debug_dir / f'ques_{i}.png').write_bytes(q)

    result = score_nine(imgs, ques)
    order, scores = result
    out = debug_dir / 'solve_result.png'
    ques_rgb = [_rgba_to_rgb(q) for q in ques]
    _draw_result(grid, scores, order, nine_nums, out, ques_imgs=ques_rgb)
    picked = [[i // 3, i % 3] for i in order[:nine_nums]]
    print(f'nine: nums={nine_nums} predicted {picked} -> {out}')


@pytest.mark.asyncio
async def test_nine_global_match_draw(cid, out_dir):
    """全局特征匹配：CLIP 向量 + Canny 边缘图对齐线稿/自然图，逐格打相似度分."""
    g, data, imgs, ques = await _load_nine_resources(cid)
    nine_nums = data['nine_nums']
    grid = cv2.imdecode(np.frombuffer(imgs, np.uint8), cv2.IMREAD_COLOR)

    assert grid is not None, 'Failed to load nine grid image'
    debug_dir = out_dir / 'solver_debug' / 'nine'
    debug_dir.mkdir(parents=True, exist_ok=True)

    extractor = get_global_feature_extractor()
    grid_img = Image.open(BytesIO(imgs)).convert('RGB')
    cells = _split_cells(grid_img)

    edge_cells = [preprocess_to_edge_map(c) for c in cells]
    cell_scores = [0.0] * 9
    for q in ques:
        edge_q = preprocess_to_edge_map(_icon_rgb(q))
        ranked = compute_cross_modal_similarity(edge_q, edge_cells, extractor)
        for idx, score in ranked:
            cell_scores[idx] += score

    order = sorted(range(9), key=lambda i: cell_scores[i], reverse=True)
    out = debug_dir / 'solve_result_global_match.png'
    _draw_result(
        grid,
        cell_scores,
        order,
        nine_nums,
        out,
        ques_imgs=[_rgba_to_rgb(q) for q in ques],
    )
    picked = [[i // 3, i % 3] for i in order[:nine_nums]]
    print(f'nine-global: nums={nine_nums} predicted {picked} -> {out}')


def _rgba_to_rgb(data: bytes) -> np.ndarray:
    img = Image.open(BytesIO(data)).convert('RGBA')
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    return cv2.cvtColor(np.array(bg.convert('RGB')), cv2.COLOR_RGB2BGR)
