"""Nine-grid (3x3) solver: neural classifier.

Scores each cell by classifying it into the target prompt icon class.
Supports custom ONNX models via auto-detected input size and node names.
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
import os
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

import numpy as np
import onnxruntime as ort
from PIL import Image

from .hub import get_model_path

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_MEAN_255 = (_MEAN * 255.0).reshape(1, 1, 3)
_INV_STD_255 = (1.0 / (_STD * 255.0)).reshape(1, 1, 3)

_BAR_MEAN = 30
_BAR_LIMIT = 8
_DEFAULT_SIZE = (128, 128)


class _ModelInfo(NamedTuple):
    session: ort.InferenceSession
    class_map: dict[str, int]
    input_name: str
    output_name: str
    input_size: tuple[int, int]  # (width, height)


def _load_classes(meta_map: dict[str, str]) -> list[str]:
    if 'classes' in meta_map:
        return [c.strip() for c in meta_map['classes'].split(',') if c.strip()]
    if 'NINE_CLASSES_PATH' in os.environ:
        p = Path(os.environ['NINE_CLASSES_PATH'])
        if p.is_file():
            content = p.read_text(encoding='utf-8').strip()
            if content.startswith('[') and content.endswith(']'):
                return json.loads(content)
            if ',' in content:
                return [c.strip() for c in content.split(',') if c.strip()]
            return [line.strip() for line in content.splitlines() if line.strip()]
    if 'NINE_CLASSES' in os.environ:
        return [c.strip() for c in os.environ['NINE_CLASSES'].split(',') if c.strip()]
    raise ValueError(
        "ONNX model is missing 'classes' metadata. "
        "Please embed 'classes' into the ONNX custom_metadata_map when exporting, "
        'or specify the class list via the NINE_CLASSES_PATH or NINE_CLASSES environment variable.'
    )


@functools.lru_cache(maxsize=1)
def _session() -> _ModelInfo:
    model_path = get_model_path()
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    if 'NINE_THREADS' in os.environ:
        options.intra_op_num_threads = int(os.environ['NINE_THREADS'])
    sess = ort.InferenceSession(
        str(model_path), options, providers=['CPUExecutionProvider']
    )

    inp = sess.get_inputs()[0]
    out = sess.get_outputs()[0]
    input_name = inp.name
    output_name = out.name

    # Determine input (width, height) from model shape [batch, 3, H, W]
    if (
        len(inp.shape) >= 4
        and isinstance(inp.shape[-2], int)
        and inp.shape[-2] > 0
        and isinstance(inp.shape[-1], int)
        and inp.shape[-1] > 0
    ):
        input_size = (inp.shape[-1], inp.shape[-2])
    else:
        input_size = _DEFAULT_SIZE

    meta_map = sess.get_modelmeta().custom_metadata_map
    classes = _load_classes(meta_map)
    class_map = {name: i for i, name in enumerate(classes)}

    return _ModelInfo(
        session=sess,
        class_map=class_map,
        input_name=input_name,
        output_name=output_name,
        input_size=input_size,
    )


def solve_nine(imgs: bytes, ques: list[bytes], nine_nums: int) -> list[list[int]]:
    """Pick the ``nine_nums`` cells that match the prompt icon.

    Returns 1-based ``[[row, col], ...]`` in click order (best first) — the SDK's
    ``userresponse`` is ``dataId``, i.e. 1..3 on both axes, not 0-based.
    Only ``ques[0]`` is used: the classifier scores against a single prompt.
    """
    order, _ = score_nine(imgs, ques)
    return [[i // 3 + 1, i % 3 + 1] for i in order[:nine_nums]]


def score_nine(imgs: bytes, ques: list[bytes]) -> tuple[list[int], list[float]]:
    """``(order, logits)`` — 9 cell indices sorted by score desc, plus raw logits."""
    logits = _logits(imgs, ques[0])
    return np.argsort(-logits).tolist(), logits.tolist()


def bar_rows(img: Image.Image) -> int:
    """底部连续纯黑的行数（CDN 图带着一条 2px 黑边）。

    用行**均值**判断，不用 max：JPEG 噪点会让个别像素偏亮，用 max 会漏检。
    """
    h = img.height
    bottom = img.crop((0, max(0, h - _BAR_LIMIT), img.width, h)).convert('RGB')
    means = np.asarray(bottom).mean(axis=(1, 2))[::-1]  # 从底往上
    dark = means < _BAR_MEAN
    if dark.all():
        return len(means)
    return int(np.argmin(dark))


def cell_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """9 个格子的 ``(left, top, right, bottom)``，行优先。

    起点用 ceil（对齐真实接缝 87 / 173），格长用 floor（三行等大），多出来的 1px 丢掉：
    259 高 → ``[0,86) [87,173) [173,259)``，三行都是 86。
    """
    xs = [math.ceil(i * width / 3) for i in range(3)]
    ys = [math.ceil(i * height / 3) for i in range(3)]
    w, h = width // 3, height // 3
    return [(xs[c], ys[r], xs[c] + w, ys[r] + h) for r in range(3) for c in range(3)]


def split_cells(img: Image.Image, *, trim_bar: bool = True) -> list[Image.Image]:
    """3x3 row-major crops, index ``row * 3 + col``；默认先裁掉底部黑边。"""
    if trim_bar and (rows := bar_rows(img)):
        img = img.crop((0, 0, img.width, img.height - rows))
    return [img.crop(box) for box in cell_boxes(img.width, img.height)]


def _prep_batch(grid: Image.Image, size: tuple[int, int] = _DEFAULT_SIZE) -> np.ndarray:
    """直接裁切 9 个格子并缩放为 (width, height) 归一化张量，形状为 (9, 3, height, width)。"""
    if rows := bar_rows(grid):
        grid = grid.crop((0, 0, grid.width, grid.height - rows))
    boxes = cell_boxes(grid.width, grid.height)
    w, h = size
    batch = np.empty((9, 3, h, w), dtype=np.float32)
    for i, box in enumerate(boxes):
        patch = grid.resize((w, h), Image.Resampling.BILINEAR, box=box)
        arr = np.asarray(patch, dtype=np.float32)
        batch[i] = ((arr - _MEAN_255) * _INV_STD_255).transpose(2, 0, 1)
    return batch


def _logits(imgs: bytes, prompt: bytes) -> np.ndarray:
    info = _session()
    prompt_hash = hashlib.md5(prompt).hexdigest()
    target_idx = info.class_map.get(prompt_hash)
    if target_idx is None:
        raise ValueError(f'Unknown nine prompt hash: {prompt_hash}')

    grid = Image.open(BytesIO(imgs)).convert('RGB')
    tensors = _prep_batch(grid, size=info.input_size)
    logits_all = np.asarray(
        info.session.run([info.output_name], {info.input_name: tensors})[0]
    )
    return logits_all[:, target_idx]


def _prep(img: Image.Image, size: tuple[int, int] = _DEFAULT_SIZE) -> np.ndarray:
    """RGBA → white-backed RGB → (width, height) → ImageNet norm, shape ``(1, 3, height, width)``."""
    if img.mode in ('RGBA', 'LA', 'P'):
        rgba = img.convert('RGBA')
        img = Image.new('RGB', rgba.size, (255, 255, 255))
        img.paste(rgba, mask=rgba.split()[3])
    w, h = size
    x = np.asarray(
        img.convert('RGB').resize((w, h), Image.Resampling.BILINEAR), np.float32
    )
    return ((x - _MEAN_255) * _INV_STD_255).transpose(2, 0, 1)[None]
