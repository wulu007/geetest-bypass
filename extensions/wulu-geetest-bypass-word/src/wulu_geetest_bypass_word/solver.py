"""Word captcha (click the characters in order): YOLO detection + PP-OCR rec embedding.

The rec model is used *only* as a feature extractor: its CTC posterior over the
whole character dictionary is a soft "which character is this" vector, so two
renderings of the same glyph land close in cosine space while different glyphs
do not. Matching therefore never needs the hard argmax (which is what a plain
``recognize_txt`` string comparison does, and it loses ~20 points of accuracy).
"""

from __future__ import annotations

import functools
import itertools
import math
import os
from collections.abc import Sequence

import cv2
import numpy as np
import onnxruntime as ort

from .hub import get_locate_model_path, get_rec_model_path

_XCYCWH = 'cxcywh'
_XYXY = 'xyxy'
_STRIDE = 8
# rec 输入的宽高比下限。PaddleOCR 默认按 320/48（T=40）补零，但单字只占 ~6 帧，
# 剩下全喂给 padding；这里降到 2.0（T=12），实测精度不变、后验耗时降 60%。
# 填充方向与填充值仍与训练一致（右填中灰）。
_MIN_RATIO = 2.0
_REC_BATCH = 8
_CANDIDATES = 5


class WordError(RuntimeError):
    """Raised when the word solver fails to detect or match characters."""


Box = tuple[int, int, int, int]


def _static_dim(dim: object, fallback: int) -> int:
    return dim if isinstance(dim, int) and dim > 0 else fallback


def _box_format(meta: dict[str, str]) -> str:
    valid_formats = (_XCYCWH, _XYXY)
    sources = (meta.get('box_format'), os.environ.get('WULU_WORD_BOX_FORMAT'))
    for val in sources:
        fmt = (val or '').strip().lower()
        if fmt in valid_formats:
            return fmt

    raise WordError(
        f"word: Missing 'box_format' in model meta. "
        f'Fix: set WORD_BOX_FORMAT env var. '
        f'Current meta: {sorted(meta)}'
    )


@functools.lru_cache(maxsize=1)
def _yolo() -> tuple[ort.InferenceSession, str, tuple[int, int], str]:
    """检测模型：输入尺寸从 graph 读，框格式从 meta 读。"""
    session = ort.InferenceSession(
        str(get_locate_model_path()), providers=['CPUExecutionProvider']
    )
    meta = session.get_modelmeta().custom_metadata_map
    if (meta.get('end2end') or 'False').strip().lower() == 'true':
        raise WordError('word: 端到端（NMS-free）检测头暂不支持，请用 anchor 格式导出')

    inp = session.get_inputs()[0]
    size = (_static_dim(inp.shape[3], 320), _static_dim(inp.shape[2], 320))
    return session, inp.name, size, _box_format(meta)


@functools.lru_cache(maxsize=1)
def _rec() -> tuple[ort.InferenceSession, str, int]:
    session = ort.InferenceSession(
        str(get_rec_model_path()), providers=['CPUExecutionProvider']
    )
    inp = session.get_inputs()[0]
    return session, inp.name, _static_dim(inp.shape[2], 48)


def _as_image(src: bytes | np.ndarray) -> np.ndarray:
    if isinstance(src, np.ndarray):
        return src

    img = cv2.imdecode(np.frombuffer(src, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise WordError('word: failed to decode image')

    ch = img.shape[2] if img.ndim == 3 else -1
    if ch == 3:
        return img
    if ch == 4:
        a = img[..., 3:4].astype(np.uint16)
        bgr = img[..., :3].astype(np.uint16)
        return ((bgr * a + 255 * (255 - a) + 127) // 255).astype(np.uint8)

    raise WordError(f'word: unexpected image shape: {img.shape}')


def _norm_image(img: np.ndarray, height: int, width: int) -> np.ndarray:
    resized_w = min(math.ceil(height * img.shape[1] / float(img.shape[0])), width)
    resized = cv2.resize(img, (resized_w, height)).astype(np.float32)
    canvas = np.zeros((3, height, width), np.float32)
    canvas[:, :, :resized_w] = (resized.transpose((2, 0, 1)) / 255 - 0.5) / 0.5
    return canvas


def _posterior(images: Sequence[np.ndarray]) -> np.ndarray:
    """每张图取非 blank 概率最大的一帧 CTC 后验，返回 ``[N, C]``。"""
    session, input_name, height = _rec()

    aligned = []
    for start in range(0, len(images), _REC_BATCH):
        chunk = list(images[start : start + _REC_BATCH])
        # 一个 batch 一个宽度：下限 _MIN_RATIO，遇到特别宽的图就跟着放宽，不会被压扁
        ratio = max(max(im.shape[1] / float(im.shape[0]) for im in chunk), _MIN_RATIO)
        width = int(height * ratio)
        blob = np.stack([_norm_image(im, height, width) for im in chunk])
        out = np.asarray(session.run(None, {input_name: blob})[0])
        for i, im in enumerate(chunk):
            resized_w = min(math.ceil(height * im.shape[1] / float(im.shape[0])), width)
            frames = max(1, round(resized_w / _STRIDE))
            seq = out[i, :frames]
            aligned.append(seq[int(np.argmax(seq[:, 1:].sum(axis=1)))])
    return np.stack(aligned)


def _assign(sim: np.ndarray) -> list[int]:
    """全局最优指派：返回每个题图对应的框下标，使总余弦最大。

    候选数只有个位数，直接穷举 ``P(m, n)`` 个排列（m=5 时 60 个），比匈牙利省事。
    """
    n, m = sim.shape
    if n > m:
        raise WordError(f'word: {n} questions but only {m} candidates')

    perms = np.array(list(itertools.permutations(range(m), n)))  # (P, n)
    return perms[np.argmax(sim[np.arange(n), perms].sum(axis=1))].tolist()


def match_chars(
    ques: Sequence[bytes | np.ndarray],
    crops: Sequence[np.ndarray],
) -> list[int]:
    """把每个题图匹配到一个候选字块，返回命中的框下标。"""
    if not crops:
        raise WordError('word: no character detected in background image')
    icons = [_as_image(q) for q in ques]
    if not icons:
        raise WordError('word: empty question list')

    features = _posterior([*icons, *crops])
    units = features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-9)
    return _assign(units[: len(icons)] @ units[len(icons) :].T)


def detect_candidates(
    src: bytes | np.ndarray,
    conf: float = 0.4,
    iou: float = 0.45,
    limit: int | None = None,
) -> list[Box]:
    """YOLO 检出候选字框，按置信度降序返回原图坐标 ``[x, y, w, h]``。"""
    session, input_name, size, fmt = _yolo()
    img = _as_image(src)
    h_orig, w_orig = img.shape[:2]

    # 1. Letterbox
    size_w, size_h = (size, size) if isinstance(size, int) else size
    r = min(size_w / w_orig, size_h / h_orig)
    nw, nh = round(w_orig * r), round(h_orig * r)
    pw, ph = (size_w - nw) // 2, (size_h - nh) // 2
    resized = cv2.resize(img, (nw, nh)) if (w_orig, h_orig) != (nw, nh) else img
    canvas = np.full((size_h, size_w, 3), 114, np.uint8)
    canvas[ph : ph + nh, pw : pw + nw] = resized

    # 2. BGR -> RGB
    blob = np.ascontiguousarray(
        canvas[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    )

    # 3. 推理与输出解析。通道数（4 + nc）远小于 anchor 数（320 输入是 2100），
    #    据此定哪一维是通道，不需要模型额外声明 nc。
    rows = np.asarray(session.run(None, {input_name: blob})[0])[0]
    if rows.shape[0] < rows.shape[1]:
        rows = rows.T  # (4 + nc, anchors) -> (anchors, 4 + nc)
    if rows.shape[1] < 5:
        raise WordError(f'word: 检测头输出 {rows.shape} 不像 (anchors, 4 + nc)')

    scores = rows[:, 4:].max(axis=1)
    mask = scores >= conf
    rows, scores = rows[mask], scores[mask]

    if len(rows) == 0:
        return []

    # 4. 坐标还原与越界裁剪
    a, b, c, d = rows[:, :4].T
    if fmt == _XYXY:
        x1, y1, x2, y2 = a, b, c, d
    else:
        x1, y1, x2, y2 = a - c / 2, b - d / 2, a + c / 2, b + d / 2
    x1 = np.clip((x1 - pw) / r, 0, w_orig)
    y1 = np.clip((y1 - ph) / r, 0, h_orig)
    x2 = np.clip((x2 - pw) / r, 0, w_orig)
    y2 = np.clip((y2 - ph) / r, 0, h_orig)

    # 5. NMS 处理（NMSBoxes 需要 [x, y, w, h] 格式）
    boxes_for_nms = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
    indices = cv2.dnn.NMSBoxes(boxes_for_nms, scores.tolist(), conf, iou)
    indices = np.asarray(indices, dtype=np.intp).flatten()
    if indices.size == 0:
        return []
    indices = indices[np.argsort(-scores[indices])]
    if limit is not None:
        indices = indices[:limit]

    # 6. 组装结果并过滤掉无效框
    result = []
    for idx in indices:
        xa, ya = int(x1[idx]), int(y1[idx])
        xb, yb = int(x2[idx]), int(y2[idx])
        width, height = xb - xa, yb - ya
        if width > 0 and height > 0:
            result.append((xa, ya, width, height))

    return result


def solve_word(bg: bytes, ques: list[bytes]) -> list[tuple[float, float]]:
    """返回每个题目字符在背景图中的归一化坐标 ``(x, y)``，范围 0.0 ~ 1.0。"""
    bg_img = _as_image(bg)
    boxes = detect_candidates(bg_img, limit=_CANDIDATES)
    if not boxes:
        raise WordError('word: no character detected in background image')
    crops = [bg_img[y : y + h, x : x + w] for x, y, w, h in boxes]
    order = match_chars(ques, crops)

    h, w = bg_img.shape[:2]
    return [
        ((boxes[i][0] + boxes[i][2] / 2) / w, (boxes[i][1] + boxes[i][3] / 2) / h)
        for i in order
    ]
