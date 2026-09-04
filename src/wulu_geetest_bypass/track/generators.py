from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .builder import TrackBuilder
from .types import Point, PointerEvent, PointerType, TrackPayload


@dataclass(frozen=True)
class BaseConfig:
    # TrackBuilder 起始点
    origin_x: Point = (0.4, 0.6)
    origin_y: Point = (0.9, 1.0)
    # 点击目标抖动范围（归一化坐标）
    jitter: float = 0.02
    # 按下到自动松开（END）的间隔区间（ms）
    release_delay: tuple[int, int] = (80, 120)
    # 点击元素尺寸
    w: float = 300.015625
    h: float = 259.6015625


@dataclass(frozen=True)
class TwoClickConfig(BaseConfig):
    # 两次点击总耗时区间（ms）
    passtime: tuple[int, int] = (4500, 9000)
    # 第一段移动到第一格的耗时占比区间
    move_ratio: tuple[float, float] = (0.35, 0.55)


@dataclass(frozen=True)
class NineConfig(BaseConfig):
    # 全程总耗时区间（ms）
    passtime: tuple[int, int] = (2500, 4000)


@dataclass(frozen=True)
class MultiClickConfig(BaseConfig):
    # 验证图片尺寸（归一化基准）
    img_w: float = 300.0
    img_h: float = 200.0
    # 提交按钮中心（容器坐标）
    submit_xy: Point = (0.5, 0.92)
    # 全程总耗时区间（ms）
    passtime: tuple[int, int] = (2500, 4000)
    # 是否在答案点击后追加一次提交按钮点击
    with_submit: bool = True


@dataclass(frozen=True)
class SlideConfig(BaseConfig):
    # TrackBuilder 起始点
    origin_x: Point = (0.3, 0.8)
    origin_y: Point = (0.85, 0.99)
    # 按下点 x 区间
    start_x: Point = (0.1, 0.15)
    # 轨迹 y 区间
    y: Point = (0.88, 0.90)
    # 按下前移动耗时区间（ms）
    press_duration: tuple[int, int] = (800, 1400)
    # 拖拽总耗时区间（ms）
    passtime: tuple[int, int] = (600, 1400)
    # 滑块元素尺寸（用于 set_left 归一化）
    w: float = 300.015625
    h: float = 261.5234375


class TrackConfig:
    slide = SlideConfig()
    svg = BaseConfig(jitter=0.01)
    winlinze = TwoClickConfig(jitter=0.04)
    match = TwoClickConfig(jitter=0.05)
    click = MultiClickConfig(jitter=0.02)
    nine = NineConfig(jitter=0.05)


def _random_origin(cfg: BaseConfig) -> Point:
    """Pick a random TrackBuilder start point from an ``origin_x``/``origin_y`` config."""
    return (random.uniform(*cfg.origin_x), random.uniform(*cfg.origin_y))


def _jitter_inside(pt: Point, jitter: float) -> Point:
    """Nudge ``pt`` by +/- ``jitter`` and clamp both coords to [0.0, 1.0]."""
    return (
        max(0.0, min(1.0, pt[0] + random.uniform(-jitter, jitter))),
        max(0.0, min(1.0, pt[1] + random.uniform(-jitter, jitter))),
    )


def _build_payload(cfg: BaseConfig, events: Sequence[PointerEvent]) -> TrackPayload:
    """Wrap built ``events`` into the full payload with an ``s``/``e`` ms window."""
    begin_ms = int(time.time() * 1000)
    return {
        'm': PointerType.MOUSE,
        'w': cfg.w,
        'h': cfg.h,
        's': begin_ms,
        'e': begin_ms + events[-1][0],
        'p': events,
    }


def _gen_click_sequence(
    cfg: MultiClickConfig | NineConfig,
    targets: Sequence[Point],
    submit: Point | None = None,
) -> tuple[TrackPayload, int]:
    """Build a multi-click track: move to each ``target`` and click, optionally
    finishing with one more click on ``submit``. Move times are split by random
    weights so the total duration (moves + release delays) lands within
    ``cfg.passtime``. Returns ``(payload, duration)``.
    """
    n = len(targets) + int(submit is not None)
    release_delays = [random.randint(*cfg.release_delay) for _ in range(n)]
    move_total = max(random.randint(*cfg.passtime) - sum(release_delays), 1)

    weights = [random.random() for _ in range(n)]
    denom = sum(weights)
    moves = [max(int(move_total * w / denom), 1) for w in weights]
    moves[-1] = max(move_total - sum(moves[:-1]), 1)

    tb = TrackBuilder(_random_origin(cfg))
    move_times = iter(moves)
    for target, delay in zip(targets, release_delays, strict=False):
        tb.move_to(*target, next(move_times)).click(delay)
    if submit is not None:
        tb.move_to(*submit, next(move_times)).click(release_delays[-1])
    events = tb.build()

    return _build_payload(cfg, events), events[-1][0]


def _gen_two_click_track(
    cfg: TwoClickConfig,
    cells: tuple[tuple[int, int], tuple[int, int]],
    center: Callable[[int, int], Point],
) -> tuple[TrackPayload, int]:
    """Shared skeleton for two-click captchas (winlinze/match).

    ``center(r, c)`` maps a 0-based grid cell to its normalized point. The track
    moves to the first cell, clicks (auto-submit DOWN+END), glides to the second
    cell and clicks again. Returns ``(payload, duration)``.
    """
    (p1, q1), (p2, q2) = cells
    target1 = _jitter_inside(center(p1, q1), cfg.jitter)
    target2 = _jitter_inside(center(p2, q2), cfg.jitter)

    passtime = random.randint(*cfg.passtime)
    release_delay = random.randint(*cfg.release_delay)
    release_delay2 = random.randint(*cfg.release_delay)
    move1 = int(passtime * random.uniform(*cfg.move_ratio))
    move2 = max(passtime - move1 - release_delay - release_delay2, 1)

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
    passtime = random.randint(*cfg.passtime)
    start = random.uniform(*cfg.start_x)
    tb.move_to(
        start, random.uniform(*cfg.y), random.randint(*cfg.press_duration)
    ).down()
    tb.move_to(start + set_left / cfg.w, random.uniform(*cfg.y), passtime).end()
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
        ((cell[1] - 0.5) / cols, (cell[0] - 0.5) / cols), cfg.jitter
    )

    release_delay = random.randint(*cfg.release_delay)
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
            (20 * c + 3) / 100 + 20.5 / cfg.w,
            (19 * r + 4) / 100 + 20.5 / cfg.h,
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


def gen_click_track(
    clicks: Sequence[Point],
    with_submit: bool | None = None,
) -> tuple[TrackPayload, int]:
    """Build a multi-click track for image-click captchas (icon/word/phrase).

    ``clicks`` is an ordered list of normalized ``(x, y)`` points, each in
    [0, 1] relative to the verification image (NOT the element). Internally they
    are scaled to element coordinates via ``img_w/img_h``, so custom solvers
    only need to return image-relative positions. The track moves to each click,
    auto-submits the trailing ``DOWN``+``END`` pair, then finally clicks the
    submit button (unless ``with_submit`` is disabled). Returns ``(payload,
    duration)``.
    """
    if not clicks:
        raise ValueError('clicks must not be empty')

    cfg = TrackConfig.click
    img_w, img_h = cfg.img_w, cfg.img_h
    el_w, el_h = cfg.w, cfg.h

    def to_element(pt: Point) -> Point:
        return (pt[0] * img_w / el_w, pt[1] * img_h / el_h)

    targets = [_jitter_inside(to_element(pt), cfg.jitter) for pt in clicks]

    if with_submit is None:
        with_submit = cfg.with_submit
    submit = None
    if with_submit:
        submit = _jitter_inside(cfg.submit_xy, cfg.jitter * 0.5)

    return _gen_click_sequence(cfg, targets, submit)


def gen_nine_track(
    cells: Sequence[tuple[int, int]], cols: int = 3
) -> tuple[TrackPayload, int]:
    """Build a multi-click track for the nine (3x3 grid) captcha.

    ``cells`` is an ordered list of 1-based ``(row, col)`` grid positions that
    the user clicks. The grid fully fills the window (no submit button — nine
    auto-submits when ``nine_nums`` cells are reached), so each click pair is a
    ``DOWN`` + ``END`` with no separate submit click. Cell centers are at
    ``((col - 0.5) / cols, (row - 0.5) / cols)``. Returns ``(payload,
    duration)``.
    """
    if not cells:
        raise ValueError('cells must not be empty')

    cfg = TrackConfig.nine
    targets = [
        _jitter_inside(((col - 0.5) / cols, (row - 0.5) / cols), cfg.jitter)
        for row, col in cells
    ]

    return _gen_click_sequence(cfg, targets)
