import random
import time
from typing import ClassVar

from .builder import TrackBuilder
from .types import Point, PointerType, TrackPayload


class TrackConfig:
    slide: ClassVar = {
        # TrackBuilder 起始点
        'origin_x': (0.3, 0.8),
        'origin_y': (0.85, 0.99),
        # 按下点 x 区间
        'start_x': (0.1, 0.15),
        # 轨迹 y 区间
        'y': (0.88, 0.90),
        # 按下前移动耗时区间（ms）
        'press_duration': (800, 1400),
        # 拖拽总耗时区间（ms）
        'passtime': (600, 1400),
        # 滑块元素尺寸（用于 set_left 归一化）
        'w': 300.015625,
        'h': 261.5234375,
    }
    svg: ClassVar = {
        # TrackBuilder 起始点
        'origin_x': (0.4, 0.6),
        'origin_y': (0.9, 1.0),
        # 点击目标抖动范围（归一化坐标）
        'jitter': 0.01,
        # 按下到自动松开（END）的间隔区间（ms）
        'release_delay': (80, 120),
        # 点击元素尺寸
        'w': 300.015625,
        'h': 259.6015625,
    }


def gen_slide_track(set_left: int) -> tuple[TrackPayload, int]:
    """Build a slide-captcha drag track for ``set_left`` px offset.

    Returns ``(payload, passtime)`` where ``payload`` is the full track payload
    (pointer type, element ``w``/``h``, interaction ``s``/``e`` window and the
    pointer events) and ``passtime`` is the drag duration in milliseconds.
    """
    cfg = TrackConfig.slide
    tb = TrackBuilder(
        (random.uniform(*cfg['origin_x']), random.uniform(*cfg['origin_y']))
    )
    passtime = random.randint(*cfg['passtime'])
    start = random.uniform(*cfg['start_x'])
    tb.move_to(
        start, random.uniform(*cfg['y']), random.randint(*cfg['press_duration'])
    ).down()
    tb.move_to(start + set_left / cfg['w'], random.uniform(*cfg['y']), passtime).end()
    events = tb.build()

    begin_ms = int(time.time() * 1000)
    payload: TrackPayload = {
        'm': PointerType.MOUSE,
        'w': cfg['w'],
        'h': cfg['h'],
        's': begin_ms,
        'e': begin_ms + events[-1][0],
        'p': events,
    }
    return payload, passtime


def gen_svg_track(
    cell: tuple[int, int],
    cols: int,
    duration: int,
) -> TrackPayload:
    """Build a click track for an SVG captcha grid cell.

    ``cell`` is the 1-based ``(row, col)`` of the target cell within a ``cols``-wide
    grid. The track starts at an origin, moves to the cell center and auto-submits
    as a trailing ``DOWN`` + ``END`` pair with no movement in between.
    ``duration`` is the total interaction time in milliseconds.
    """
    cfg = TrackConfig.svg
    origin = (random.uniform(*cfg['origin_x']), random.uniform(*cfg['origin_y']))
    target: Point = (
        (cell[1] - 0.5) / cols + random.uniform(-cfg['jitter'], cfg['jitter']),
        (cell[0] - 0.5) / cols + random.uniform(-cfg['jitter'], cfg['jitter']),
    )
    target = (max(0.0, min(1.0, target[0])), max(0.0, min(1.0, target[1])))

    release_delay = random.randint(*cfg['release_delay'])
    move_duration = max(duration - release_delay, 1)

    tb = TrackBuilder(origin)
    tb.move_to(*target, move_duration).click(release_delay)
    events = tb.build()

    begin_ms = int(time.time() * 1000)
    payload: TrackPayload = {
        'm': PointerType.MOUSE,
        'w': cfg['w'],
        'h': cfg['h'],
        's': begin_ms,
        'e': begin_ms + events[-1][0],
        'p': events,
    }
    return payload
