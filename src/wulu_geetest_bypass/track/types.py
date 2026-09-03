from collections.abc import Sequence
from enum import IntEnum
from typing import TypedDict

_PERCENT_PRECISION = 4


class TrackType(IntEnum):
    START = 0
    MOVE = 1
    END = 2
    DOWN = 3


class PointerType(IntEnum):
    UNKNOWN = 0
    MOUSE = 1
    TOUCH = 2
    PEN = 3


PointerEvent = tuple[int, float, float, TrackType | int]
""" A pointer event is represented as a tuple of four elements"""
Point = tuple[float, float]


def _percent_round(point: Point) -> Point:
    return (
        round(point[0], _PERCENT_PRECISION),
        round(point[1], _PERCENT_PRECISION),
    )


class TrackPayload(TypedDict):
    m: PointerType | int
    """ Pointer type: 0=unknown, 1=mouse, 2=touch, 3=pen """
    w: float
    """ Width of the element being interacted with """
    h: float
    """ Height of the element being interacted with """
    s: int
    """ Start time of the interaction """
    e: int
    """ End time of the interaction """
    p: Sequence[PointerEvent]
    """ List of pointer events, each represented as a tuple of (timestamp, x, y, track_type) """
