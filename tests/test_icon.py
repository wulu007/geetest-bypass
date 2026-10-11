import hashlib
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from wulu_geetest_bypass import Geetest

pytest.importorskip('wulu_geetest_bypass_icon')

from wulu_geetest_bypass_icon._config import DIR_HASHES
from wulu_geetest_bypass_icon.solver import _detect, _match_direction

_MODEL_ENV = 'WULU_ICON_MODEL'
_CID = 'af29b3003fc94f2ba29e865b31ee86ee'
# Repo-local model, so the test never hits the network.
_MODEL = Path(__file__).resolve().parents[1] / 'resources' / 'icon_yolo.onnx'
os.environ.setdefault(_MODEL_ENV, str(_MODEL))


async def _load_icon():
    g = Geetest(captcha_id=_CID, risk_type='icon')
    data = await g.load()
    return await g._load_resources(data['imgs'], *data['ques'])


def _solve_each(bg, ques):
    """Answer each question on its own; unknown directions are noted, not raised."""
    h, w = bg.shape[:2]
    detections = _detect(bg)
    used: set[int] = set()
    clicks = []
    notes = []
    for i, q in enumerate(ques):
        direction = DIR_HASHES.get(hashlib.md5(q).hexdigest())
        center = (
            _match_direction(direction, detections, used, h, w) if direction else None
        )
        clicks.append(center)
        notes.append(
            f'ques#{i + 1}: {direction or "UNKNOWN_TYPE"} {"OK" if center else "NO-MATCH"}'
        )
    return detections, clicks, notes


def _ques_bar(ques, width, height, pad=8):
    """Question icons stitched onto a light bar ``width`` wide.

    The icons are black with an alpha mask, so they need a light backdrop —
    on the old dark panel they rendered as nothing.
    """
    bar = np.full((height + 2 * pad, width, 3), 245, np.uint8)
    x = pad
    for q in ques:
        img = cv2.imdecode(np.frombuffer(q, np.uint8), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        scale = height / img.shape[0]
        img = cv2.resize(
            img,
            (max(1, round(img.shape[1] * scale)), height),
            interpolation=cv2.INTER_AREA,
        )
        tile = img[:, :, :3].astype(np.float32)
        if img.shape[2] == 4:
            alpha = img[:, :, 3:4].astype(np.float32) / 255.0
            tile = tile * alpha + 245.0 * (1.0 - alpha)
        tile = tile.astype(np.uint8)
        if x + tile.shape[1] > width - pad:
            break
        bar[pad : pad + height, x : x + tile.shape[1]] = tile
        x += tile.shape[1] + pad
    return bar


def _draw(bg, detections, clicks, ques):
    canvas = bg[:, :, :3].copy()
    h, w = canvas.shape[:2]

    for d in detections:
        x1, y1, x2, y2 = d['bbox']
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            canvas,
            f'{d["direction"]} {d["conf"]:.2f}',
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

    for i, c in enumerate(clicks):
        if c is None:
            continue
        cv2.putText(
            canvas,
            str(i + 1),
            (int(c[0] * w) - 7, int(c[1] * h) + 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )

    return np.vstack([_ques_bar(ques, w, max(24, min(72, h // 4))), canvas])


@pytest.mark.asyncio
async def test_icon_draw(out_dir):
    imgs, *ques = await _load_icon()
    bg = cv2.imdecode(np.frombuffer(imgs, np.uint8), cv2.IMREAD_UNCHANGED)
    assert bg is not None

    detections, clicks, notes = _solve_each(bg, ques)
    print(*notes, sep='\n')
    print(f'model={os.environ.get(_MODEL_ENV)} detections={len(detections)}')

    for c in clicks:
        assert c is None or (0 <= c[0] <= 1 and 0 <= c[1] <= 1)

    canvas = _draw(bg, detections, clicks, ques)
    out = out_dir / 'icon.png'
    cv2.imwrite(str(out), canvas)
    print(f'icon: {out}')
