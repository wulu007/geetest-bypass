import random
import time
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from .builder import TrackBuilder
from .types import Point, PointerEvent, PointerType, TrackPayload

# 点击/棋盘类验证码的公共配置（winlinze/match 额外带 passtime/move_ratio）
_CLICK_BASE: dict[str, Any] = {
    # TrackBuilder 起始点
    'origin_x': (0.4, 0.6),
    'origin_y': (0.9, 1.0),
    # 点击目标抖动范围（归一化坐标）
    'jitter': 0.04,
    # 按下到自动松开（END）的间隔区间（ms）
    'release_delay': (80, 120),
    # 点击元素尺寸
    'w': 300.015625,
    'h': 259.6015625,
}
_TWO_CLICK_BASE: dict[str, Any] = {
    **_CLICK_BASE,
    # 两次点击总耗时区间（ms）
    'passtime': (4500, 9000),
    # 第一段移动到第一格的耗时占比区间
    'move_ratio': (0.35, 0.55),
}


class TrackConfig:
    slide: ClassVar[dict[str, Any]] = {
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
    svg: ClassVar[dict[str, Any]] = {**_CLICK_BASE, 'jitter': 0.01}
    winlinze: ClassVar[dict[str, Any]] = {**_TWO_CLICK_BASE, 'jitter': 0.04}
    match: ClassVar[dict[str, Any]] = {**_TWO_CLICK_BASE, 'jitter': 0.05}


def _random_origin(cfg: dict[str, Any]) -> Point:
    """Pick a random TrackBuilder start point from an ``origin_x``/``origin_y`` config."""
    return (random.uniform(*cfg['origin_x']), random.uniform(*cfg['origin_y']))


def _jitter_inside(pt: Point, jitter: float) -> Point:
    """Nudge ``pt`` by +/- ``jitter`` and clamp both coords to [0.0, 1.0]."""
    return (
        max(0.0, min(1.0, pt[0] + random.uniform(-jitter, jitter))),
        max(0.0, min(1.0, pt[1] + random.uniform(-jitter, jitter))),
    )


def _build_payload(cfg: dict[str, Any], events: Sequence[PointerEvent]) -> TrackPayload:
    """Wrap built ``events`` into the full payload with an ``s``/``e`` ms window."""
    begin_ms = int(time.time() * 1000)
    return {
        'm': PointerType.MOUSE,
        'w': cfg['w'],
        'h': cfg['h'],
        's': begin_ms,
        'e': begin_ms + events[-1][0],
        'p': events,
    }


def _gen_two_click_track(
    cfg: dict[str, Any],
    cells: tuple[tuple[int, int], tuple[int, int]],
    center: Callable[[int, int], Point],
) -> tuple[TrackPayload, int]:
    """Shared skeleton for two-click captchas (winlinze/match).

    ``center(r, c)`` maps a 0-based grid cell to its normalized point. The track
    moves to the first cell, clicks (auto-submit DOWN+END), glides to the second
    cell and clicks again. Returns ``(payload, duration)``.
    """
    (p1, q1), (p2, q2) = cells
    target1 = _jitter_inside(center(p1, q1), cfg['jitter'])
    target2 = _jitter_inside(center(p2, q2), cfg['jitter'])

    passtime = random.randint(*cfg['passtime'])
    release_delay = random.randint(*cfg['release_delay'])
    release_delay2 = random.randint(*cfg['release_delay'])
    move1 = int(passtime * random.uniform(*cfg['move_ratio']))
    move2 = max(passtime - move1 - release_delay, 1)

    tb = TrackBuilder(_random_origin(cfg))
    tb.move_to(*target1, move1).click(release_delay)
    tb.move_to(*target2, move2).click(release_delay2)
    events = tb.build()

    return _build_payload(cfg, events), events[-1][0]


def gen_slide_track(set_left: int) -> tuple[TrackPayload, int]:
    """Build a slide-captcha drag track for ``set_left`` px offset.

    Returns ``(payload, passtime)`` where ``payload`` is the full track payload
    (pointer type, element ``w``/``h``, interaction ``s``/``e`` window and the
    pointer events) and ``passtime`` is the drag duration in milliseconds.
    """
    cfg = TrackConfig.slide
    tb = TrackBuilder(_random_origin(cfg))
    passtime = random.randint(*cfg['passtime'])
    start = random.uniform(*cfg['start_x'])
    tb.move_to(
        start, random.uniform(*cfg['y']), random.randint(*cfg['press_duration'])
    ).down()
    tb.move_to(start + set_left / cfg['w'], random.uniform(*cfg['y']), passtime).end()
    events = tb.build()

    return _build_payload(cfg, events), passtime


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
    target = _jitter_inside(
        ((cell[1] - 0.5) / cols, (cell[0] - 0.5) / cols), cfg['jitter']
    )

    release_delay = random.randint(*cfg['release_delay'])
    move_duration = max(duration - release_delay, 1)

    tb = TrackBuilder(_random_origin(cfg))
    tb.move_to(*target, move_duration).click(release_delay)
    events = tb.build()

    return _build_payload(cfg, events)


def gen_winlinze_track(
    cells: tuple[tuple[int, int], tuple[int, int]],
) -> tuple[TrackPayload, int]:
    """Build a two-click track for the winlinze (goban) captcha.

    ``cells`` is a pair of 0-based ``(row, col)`` positions — the piece to move
    and the empty target that wins the game. Each cell center is derived from the
    absolute-positioned 5x5 board layout (``left: 20*col+3%``, ``top: 19*row+4%``,
    41px cell side) and jittered within the cell.
    """
    cfg = TrackConfig.winlinze

    def center(r: int, c: int) -> Point:
        return (
            (20 * c + 3) / 100 + 20.5 / cfg['w'],
            (19 * r + 4) / 100 + 20.5 / cfg['h'],
        )

    return _gen_two_click_track(cfg, cells, center)


def gen_match_track(
    cells: tuple[tuple[int, int], tuple[int, int]],
) -> tuple[TrackPayload, int]:
    """Build a two-click track for the match (3-in-a-row) captcha.

    ``cells`` is a pair of 0-based ``(first, second)`` positions — two adjacent
    cells swapped to complete a line. The 3x3 grid fully fills the window, each
    cell at ``33.4%`` steps (``left: 33.4*first%, top: 33.4*second%``).
    """
    cfg = TrackConfig.match

    def center(i: int, j: int) -> Point:
        return (
            (33.4 * i + 16.7) / 100,
            (33.4 * j + 16.7) / 100,
        )

    return _gen_two_click_track(cfg, cells, center)
