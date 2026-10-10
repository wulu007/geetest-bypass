from __future__ import annotations

import ast
import functools
import hashlib
from typing import TypedDict

import cv2
import numpy as np

from ._config import (
    CONF_THRES,
    DIR_HASHES,
    DIR_NAMES,
    IOU_THRES,
    MAX_DET,
)
from .download import resolve_model


class Detection(TypedDict):
    direction: str
    bbox: list[int]
    conf: float


class UnsupportedQuestionError(NotImplementedError):
    """Raised when a question icon cannot be answered reliably."""


class UnsupportedModelError(RuntimeError):
    """Raised when the ONNX model does not match what the solver expects."""


def solve_icon(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]:
    """Locate each direction-type question icon inside the background image.

    Each question's MD5 (``DIR_HASHES``) recovers its arrow direction; the
    YOLO model locates the background icon facing that direction. A question
    whose MD5 is not in the table — or a direction that yields no detection —
    raises ``UnsupportedQuestionError`` rather than guessing.

    Returns one normalized ``(x, y)`` center per question icon (in question
    order), both components in ``[0, 1]`` relative to the background image.
    """
    bg = _decode(imgs)
    if bg is None:
        raise ValueError('icon: failed to decode background image')

    h, w = bg.shape[:2]
    detections = _detect(bg)

    used: set[int] = set()
    clicks: list[tuple[float, float]] = []
    for ques_img in ques:
        q_hash = hashlib.md5(ques_img).hexdigest()
        direction = DIR_HASHES.get(q_hash)
        if direction is None:
            raise UnsupportedQuestionError(
                f'icon: question MD5 {q_hash!r} is not a known direction asset'
            )

        center = _match_direction(direction, detections, used, h, w)
        if center is None:
            raise UnsupportedQuestionError(
                f'icon: no background detection for direction {direction!r}'
            )
        clicks.append(center)

    return clicks


def _match_direction(
    direction: str,
    detections: list[Detection],
    used: set[int],
    h: int,
    w: int,
) -> tuple[float, float] | None:
    unused = [i for i in range(len(detections)) if i not in used]
    # 只找严格相等的，找不到直接返回 None（触发报错）
    chosen = next((i for i in unused if detections[i]['direction'] == direction), None)
    if chosen is None:
        return None

    x1, y1, x2, y2 = detections[chosen]['bbox']
    used.add(chosen)
    return (
        min(1.0, max(0.0, (x1 + (x2 - x1) / 2.0) / w)),
        min(1.0, max(0.0, (y1 + (y2 - y1) / 2.0) / h)),
    )


@functools.lru_cache(maxsize=1)
def _maybe_session():
    model_path = resolve_model()
    import onnxruntime as ort

    return ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])


@functools.lru_cache(maxsize=1)
def _dir_names() -> tuple[str, ...]:
    """Direction names in channel order; model metadata first, ``DIR_NAMES`` last."""
    meta = _maybe_session().get_modelmeta().custom_metadata_map
    if meta.get('end2end') == 'True':
        raise UnsupportedModelError('model has built-in NMS (end2end=True)')

    raw = meta.get('names')
    if raw is None:
        names = tuple(DIR_NAMES)
    else:
        parsed = ast.literal_eval(raw)  # ultralytics writes "{0: 'u', 1: 'd', ...}"
        names = tuple(parsed[i] for i in sorted(parsed))

    known = sorted(DIR_HASHES.values())
    if sorted(names) != known:
        raise UnsupportedModelError(f'model classes {sorted(names)} != {known}')
    return names


def _get_letterbox_params(
    img_shape: tuple[int, int],
    target_shape: tuple[int, int],
) -> tuple[float, int, int, int, int]:
    h, w = img_shape
    in_h, in_w = target_shape
    r = min(in_w / w, in_h / h)
    new_w, new_h = round(w * r), round(h * r)
    pad_w = (in_w - new_w) // 2
    pad_h = (in_h - new_h) // 2
    return r, new_w, new_h, pad_w, pad_h


def _letterbox_blob(img: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    in_h, in_w = shape
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        bgr = img[:, :, :3].astype(np.float32)
        img = (bgr * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)

    _, new_w, new_h, pad_w, pad_h = _get_letterbox_params(img.shape[:2], shape)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((in_h, in_w, 3), 114, np.uint8)
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized
    blob = canvas[..., ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.ascontiguousarray(blob[None])


def _detect(bg: np.ndarray, max_det: int = MAX_DET) -> list[Detection]:
    """Detect up to ``max_det`` direction icons in ``bg``.

    Boxes are returned in background-image pixels, clipped to the image.
    """
    h, w = bg.shape[:2]
    names = _dir_names()
    boxes, confs, cls_ids = _predict(bg)
    keep = _nms(boxes, confs)[:max_det]
    clipped = np.clip(boxes[keep], (0, 0, 0, 0), (w, h, w, h))

    return [
        {
            'direction': names[c],
            'bbox': b.astype(int).tolist(),
            'conf': float(p),
        }
        for c, p, b in zip(cls_ids[keep], confs[keep], clipped, strict=True)
    ]


def _predict(bg: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    session = _maybe_session()
    inp = session.get_inputs()[0]
    in_h, in_w = int(inp.shape[2]), int(inp.shape[3])
    nc = len(_dir_names())

    blob = _letterbox_blob(bg, (in_h, in_w))
    raw = session.run([session.get_outputs()[0].name], {inp.name: blob})[0]
    # pyrefly: ignore [no-matching-overload]
    preds = np.squeeze(raw, axis=0).T  # (num_preds, 4 + nc)
    if preds.shape[1] != 4 + nc:
        raise UnsupportedModelError(
            f'model output has {preds.shape[1]} channels, expected {4 + nc}'
        )

    confs = preds[:, 4 : 4 + nc].max(axis=1)
    cls_ids = preds[:, 4 : 4 + nc].argmax(axis=1)

    # cxcywh → xyxy，反向 letterbox 还原到背景图坐标
    h0, w0 = bg.shape[:2]
    r, _, _, pad_w, pad_h = _get_letterbox_params((h0, w0), (in_h, in_w))
    keep = confs >= CONF_THRES
    cx, cy, bw, bh = preds[keep, :4].T
    boxes = np.stack(
        (
            (cx - bw / 2 - pad_w) / r,
            (cy - bh / 2 - pad_h) / r,
            (cx + bw / 2 - pad_w) / r,
            (cy + bh / 2 - pad_h) / r,
        ),
        axis=1,
    )
    return boxes, confs[keep], cls_ids[keep]


def _nms(boxes: np.ndarray, confs: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = np.argsort(-confs)
    keep: list[int] = []

    while order.size:
        i = int(order[0])
        keep.append(i)

        rest = order[1:]
        if rest.size == 0:
            break

        ix1 = np.maximum(x1[i], x1[rest])
        iy1 = np.maximum(y1[i], y1[rest])
        ix2 = np.minimum(x2[i], x2[rest])
        iy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0, ix2 - ix1) * np.maximum(0, iy2 - iy1)

        union = areas[i] + areas[rest] - inter
        iou = inter / (union + 1e-7)
        order = rest[iou <= IOU_THRES]

    return np.array(keep, dtype=np.int64)


def _decode(data: bytes) -> np.ndarray | None:
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
