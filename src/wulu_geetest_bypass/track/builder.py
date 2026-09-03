import math
import random
from collections.abc import Iterator, Sequence
from typing import Self

from .types import (
    Point,
    PointerEvent,
    TrackType,
    _percent_round,
)


def gen_timestamps(
    duration: int,
    base_time: int = 0,
    base_interval: int = 17,
    max_extra: int = 10,
    min_interval: int = 17,
) -> Iterator[int]:
    """Yield increasing timestamps from ``base_time`` up to ``base_time + duration``.

    Intervals are randomized around ``base_interval`` to mimic human sampling.
    """
    if duration <= 0:
        yield base_time
        return

    cur = 0
    yield cur + base_time
    while duration - cur >= min_interval:
        interval = base_interval + random.randint(0, max_extra)
        if interval < min_interval:
            interval = min_interval
        next_time = cur + interval
        if duration - next_time >= min_interval:
            yield next_time + base_time
            cur = next_time
        else:
            break
    yield duration + base_time


def generate_control_points(start: Point, end: Point) -> tuple[Point, Point]:
    """Sample two cubic-bezier control points between ``start`` and ``end``.

    Control points are placed along the segment (30%-70%) with a random lateral
    offset so the resulting curve looks hand-drawn. Degenerates to a straight
    line for near-zero distances.
    """
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    distance = math.hypot(dx, dy)

    offset_base = min(0.2, max(0.05, distance * 0.3))
    angle1 = random.uniform(-math.pi, math.pi)
    angle2 = random.uniform(-math.pi, math.pi)
    offset1 = offset_base * random.uniform(0.5, 1.0)
    offset2 = offset_base * random.uniform(0.5, 1.0)

    cx1 = x0 + dx * random.uniform(0.3, 0.7) + math.cos(angle1) * offset1
    cy1 = y0 + dy * random.uniform(0.3, 0.7) + math.sin(angle1) * offset1
    cx2 = x1 - dx * random.uniform(0.3, 0.7) + math.cos(angle2) * offset2
    cy2 = y1 - dy * random.uniform(0.3, 0.7) + math.sin(angle2) * offset2

    if distance < 0.01:
        cx1, cy1 = x0, y0
        cx2, cy2 = x1, y1

    return (cx1, cy1), (cx2, cy2)


def bezier_point(t: float, p0: Point, p1: Point, cp1: Point, cp2: Point) -> Point:
    """Evaluate the cubic bezier curve defined by ``p0``/``p1``/``cp1``/``cp2``."""
    x0, y0 = p0
    x1, y1 = p1
    cx1, cy1 = cp1
    cx2, cy2 = cp2

    mt = 1 - t
    x = mt**3 * x0 + 3 * mt**2 * t * cx1 + 3 * mt * t**2 * cx2 + t**3 * x1
    y = mt**3 * y0 + 3 * mt**2 * t * cy1 + 3 * mt * t**2 * cy2 + t**3 * y1
    return x, y


def _gen_track(
    start: Point, end: Point, duration: int, base_time: int = 0
) -> Sequence[PointerEvent]:
    """Generate pointer events along a smooth bezier path from ``start`` to ``end``.

    Timestamps span ``base_time`` .. ``base_time + duration``; coordinates are
    normalized to [0, 1] and rounded to :data:`_PERCENT_PRECISION`.
    """
    times = list(gen_timestamps(duration, base_time))
    total_duration = times[-1] - times[0]

    cp1, cp2 = generate_control_points(start, end)

    def ease(t: float) -> float:
        return 3 * t * t - 2 * t * t * t

    # Segment start point
    events: list[PointerEvent] = [
        (
            times[0],
            *_percent_round(start),
            TrackType.MOVE,
        )
    ]

    # Intermediate MOVE samples along the bezier path with jitter
    for i in range(1, len(times) - 1):
        t = times[i]
        progress = (t - times[0]) / total_duration
        eased = ease(progress)
        # pyrefly: ignore [bad-argument-type]
        x, y = bezier_point(eased, start, end, cp1, cp2)
        x += random.uniform(-0.002, 0.002)
        y += random.uniform(-0.002, 0.002)
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        events.append((t, *_percent_round((x, y)), TrackType.MOVE))

    # Segment end point
    events.append((times[-1], *_percent_round(end), TrackType.MOVE))
    return events


class TrackBuilder:
    """Fluent builder that concatenates track segments onto one continuous timeline.

    Each :meth:`move_to` continues from the previous event's timestamp, so a
    multi-segment track stays strictly time-ordered. Call :meth:`end` before
    :meth:`build`.
    """

    def __init__(self, start: Point):
        self._cur = self.start_point = start
        self.end_point: Point
        self.down_points: list[Point] = []
        self.duration: int = 0
        self.max_points: int = 150
        self.keep_before_click: int = 150
        self._events: list[PointerEvent] = [
            (0, *_percent_round(start), TrackType.START)
        ]

    def down(self) -> Self:
        """Mark the current position as a pointer-down (click) point."""
        self.down_points.append(self._cur)
        e = self._events[-1]
        self._events[-1] = (*e[:3], TrackType.DOWN)
        return self

    def move_to(self, x: float, y: float, duration: int) -> Self:
        """Append a segment moving to ``(x, y)`` over ``duration`` ms.

        The joint point is dropped since it duplicates the previous segment's
        end position and timestamp.
        """
        events = _gen_track(self._cur, (x, y), duration, self._events[-1][0])
        self._events.extend(events[1:])
        self._cur = (x, y)
        self.duration += duration
        return self

    def end(self) -> Self:
        """Mark the current position as the final END event."""
        self.end_point = self._cur
        e = self._events[-1]
        self._events[-1] = (*e[:3], TrackType.END)
        return self

    def build(self) -> Sequence[PointerEvent]:
        if self.start_point is None or self.end_point is None or self.duration <= 0:
            raise ValueError('Must set start, end, and duration before building')
        return self._compress(self._events)

    def _compress(self, track: list[PointerEvent]) -> list[PointerEvent]:
        """Downsample ``track`` to at most ``max_points`` while keeping order.

        Points near the end (within ``keep_before_click`` ms) are preferred so
        click/release actions keep fine-grained context; older points fill the
        remaining budget.
        """
        if len(track) <= self.max_points:
            return track

        # Separate regular move points from key action points
        moves = [p for p in track if p[3] == TrackType.MOVE]
        non_moves = [p for p in track if p[3] != TrackType.MOVE]

        # Pick the newest points near the end first
        first = (0, *self.start_point, TrackType.START)
        need = self.max_points - len(self.down_points) - 2
        end_time = track[-1][0]
        near_end = [p for p in moves if end_time - p[0] <= self.keep_before_click]
        selected = near_end[-need:] if len(near_end) >= need else near_end[:]

        if len(selected) < need:
            older = [p for p in moves if p not in near_end]
            need_more = need - len(selected)
            for p in reversed(older):
                if need_more <= 0:
                    break
                selected.insert(0, p)
                need_more -= 1

        # Merge back; insertion order already keeps chronological order
        return [first, *selected, *non_moves]
