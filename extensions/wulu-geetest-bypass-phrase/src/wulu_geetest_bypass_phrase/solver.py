"""Phrase captcha (click the four characters in order).

:func:`_locate` finds the four boxes, :func:`_recognize` reads one CJK character per box,
:func:`_order` gives the click order. Models and the dictionary come from :mod:`.hub`.
"""

from __future__ import annotations

import functools
import itertools
import json
import re

import cv2
import numpy as np
import onnxruntime as ort

from .hub import (
    get_detect_model_path,
    get_dict_path,
    get_order_model_path,
    get_tokenizer_path,
)

_CJK = re.compile(r'[\u4e00-\u9fff]')


@functools.lru_cache(maxsize=1)
def _session():
    return ort.InferenceSession(
        get_detect_model_path(), providers=['CPUExecutionProvider']
    )


@functools.lru_cache(maxsize=1)
def _ocr():
    from rapidocr import RapidOCR

    return RapidOCR(
        params={
            'Global.use_det': False,
            'Global.use_cls': False,
            'Global.log_level': 'error',
        }
    )


@functools.lru_cache(maxsize=1)
def _dict() -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    """``dict.json`` 的三段：验证过的答案 / 失败记忆 / 手工候选。"""
    data = json.loads(get_dict_path().read_text(encoding='utf-8'))
    return data['table'], data['tried'], data['pending']


@functools.lru_cache(maxsize=1)
def _order_session():
    # 模型小（3.17M 参数、6 token），多线程反而更慢
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        get_order_model_path(), options, providers=['CPUExecutionProvider']
    )


@functools.lru_cache(maxsize=1)
def _order_tokenizer():
    from tokenizers import Tokenizer

    return Tokenizer.from_file(str(get_tokenizer_path()))


def solve_phrase(bg: bytes) -> list[tuple[float, float]]:
    """定位 -> 识别 -> 语序还原，返回归一化点击坐标（0~1）；没凑齐 4 个字返回空表。"""
    img = cv2.imdecode(np.frombuffer(bg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('failed to decode image')
    boxes = _locate(img)
    chars = _recognize(img, boxes)
    if len(boxes) != 4 or len(chars) != 4 or any(not c for c in chars):
        return []
    h, w = img.shape[:2]
    clicks = []
    for i in _order(chars):
        x, y, bw, bh = boxes[i]
        clicks.append(((x + bw / 2) / w, (y + bh / 2) / h))
    return clicks


def _order(chars: list[str]) -> tuple[int, ...]:
    """语序还原：字典 -> 手工候选 -> ``order.onnx``，返回点击顺序（框下标）。

    4 个字里有重复字时字典不参与（排序串分不出同字落在哪个框）。
    """
    key = ''.join(sorted(chars))
    table, tried, pending = _dict()
    if len(set(chars)) == len(chars) and (phrase := table.get(key)):
        order = _indices(chars, phrase)
        if order is not None:
            return order

    bad = {_indices(chars, p) for p in tried.get(key, ())}  # tried 是语序串，先翻成下标
    ranked = [p for p in _rank(chars) if p not in bad]
    hint = _indices(chars, pending.get(key, ''))  # 手工候选，有效就提到最前
    if hint is not None and hint in ranked:
        ranked.remove(hint)
        ranked.insert(0, hint)
    return ranked[0] if ranked else tuple(range(len(chars)))


def _matrix(chars: list[str]) -> np.ndarray:
    """打分矩阵：``M[i, k]`` = 第 i 个字排在位置 k 的分数（丢掉 ``[CLS]``/``[SEP]``）。"""
    session = _order_session()
    ids = np.array([_order_tokenizer().encode(''.join(chars)).ids], np.int64)
    expected_len = len(chars) + 2
    if ids.shape[1] != expected_len:
        raise ValueError(f'tokenizer 给出 {ids.shape[1]} 个 token，期望 {expected_len}')

    names = [inp.name for inp in session.get_inputs()]
    if len(names) != 2:
        raise ValueError(
            f'order.onnx 有 {len(names)} 个输入，期望 input_ids 与 attention_mask'
        )
    logits = session.run(None, {names[0]: ids, names[1]: np.ones_like(ids)})[0]
    # pyrefly: ignore [bad-index]
    return logits[0, 1 : len(chars) + 1]


@functools.lru_cache(maxsize=4)
def _perms(n: int) -> np.ndarray:
    """``(n!, n)`` 的排列下标表，第 j 行是第 j 个排列。"""
    return np.array(list(itertools.permutations(range(n))))


def _rank(chars: list[str]) -> list[tuple[int, ...]]:
    """全部点击顺序按模型总分降序，同分按排列本身的先后。"""
    matrix = _matrix(chars)
    perms = _perms(len(chars))
    totals = matrix[perms, np.arange(len(chars))].sum(axis=1)
    return [tuple(perms[j].tolist()) for j in np.argsort(-totals, kind='stable')]


def _indices(chars: list[str], phrase: str) -> tuple[int, ...] | None:
    """把语序映射回字框下标；每个下标只用一次。对不上返回 ``None``。"""
    used: list[int] = []
    for ch in phrase:
        i = next((j for j, c in enumerate(chars) if c == ch and j not in used), None)
        if i is None:
            return None
        used.append(i)
    return tuple(used)


def _locate(img: np.ndarray, *, conf: float = 0.70, iou: float = 0.45):
    session = _session()
    inp, out = session.get_inputs()[0], session.get_outputs()[0]
    # (batch, channels, height, width)
    size = int(inp.shape[2])
    h, w = img.shape[:2]

    r = min(size / w, size / h)
    nw, nh = round(w * r), round(h * r)
    pw, ph = (size - nw) // 2, (size - nh) // 2
    canvas = np.full((size, size, 3), 114, np.uint8)
    canvas[ph : ph + nh, pw : pw + nw] = cv2.resize(img, (nw, nh))
    blob = np.ascontiguousarray(
        canvas[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255
    )

    # pyrefly: ignore [bad-index]
    preds = session.run([out.name], {inp.name: blob})[0][0].T
    assert preds.shape[1] == 5, (
        f'model output has {preds.shape[1]} channels, expected 5'
    )

    preds = preds[preds[:, 4] >= conf]
    if not len(preds):
        return []

    cx, cy, bw, bh = preds[:, :4].T
    x1 = np.clip((cx - bw / 2 - pw) / r, 0, w)
    y1 = np.clip((cy - bh / 2 - ph) / r, 0, h)
    x2 = np.clip((cx + bw / 2 - pw) / r, 0, w)
    y2 = np.clip((cy + bh / 2 - ph) / r, 0, h)

    boxes = []
    for i in _nms(x1, y1, x2, y2, preds[:, 4], iou):
        xa, ya, xb, yb = int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])
        width, height = xb - xa, yb - ya
        if width > 0 and height > 0:
            boxes.append((xa, ya, width, height))
    return boxes


def _nms(x1, y1, x2, y2, scores, iou: float) -> list[int]:
    areas = (x2 - x1) * (y2 - y1)
    order = np.argsort(-scores, kind='stable')  # 分数降序，同分按原下标
    keep: list[int] = []
    while order.size:
        top = int(order[0])
        keep.append(top)
        rest = order[1:]
        if not rest.size:
            break
        inter = np.maximum(
            0.0, np.minimum(x2[top], x2[rest]) - np.maximum(x1[top], x1[rest])
        ) * np.maximum(
            0.0, np.minimum(y2[top], y2[rest]) - np.maximum(y1[top], y1[rest])
        )
        union = np.maximum(areas[top] + areas[rest] - inter, 1e-9)
        order = rest[inter / union <= iou]
    return keep


def _recognize(img: np.ndarray, boxes) -> list[str]:
    if not boxes:
        return []
    crops = [img[y : y + bh, x : x + bw] for x, y, bw, bh in boxes]
    txts = _ocr().recognize_txt(crops).txts or ()
    chars = [''] * len(boxes)
    for i, txt in enumerate(txts[: len(boxes)]):
        if m := _CJK.search(txt):
            chars[i] = m.group()
    return chars
