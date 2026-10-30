import json
import time


def format_userresponse(clicks: list[tuple[float, float]]) -> list[list[int]]:
    """Convert a list of (x, y) clicks to the userresponse format."""
    return [[round(x * 10000), round(y * 10000)] for x, y in clicks]


def unwrap_jsonp(text: str) -> dict:
    t = text.strip()
    return json.loads(t[t.index('(') + 1 : t.rindex(')')])


def gt_callback() -> str:
    return f'geetest_{int(time.time() * 1000)}'
