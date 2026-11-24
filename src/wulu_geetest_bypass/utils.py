import json
import random
import time

from wreq import Emulation, Platform, Profile

CHROME_PROFILES: tuple[Profile, ...] = tuple(
    p
    for browser in ('Chrome', 'Edge')
    for ver in range(140, 148)
    if (p := getattr(Profile, f'{browser}{ver}', None)) is not None
)


def random_emulation(platform: Platform = Platform.Windows) -> Emulation:
    """Pick a random modern Chrome profile paired with ``platform``."""
    return Emulation(random.choice(CHROME_PROFILES), platform)


def format_userresponse(clicks: list[tuple[float, float]]) -> list[list[int]]:
    """Convert a list of (x, y) clicks to the userresponse format."""
    return [[round(x * 10000), round(y * 10000)] for x, y in clicks]


def unwrap_jsonp(text: str) -> dict:
    t = text.strip()
    return json.loads(t[t.index('(') + 1 : t.rindex(')')])


def gt_callback() -> str:
    return f'geetest_{int(time.time() * 1000)}'
