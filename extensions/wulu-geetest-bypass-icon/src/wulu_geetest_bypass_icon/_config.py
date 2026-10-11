"""Constants and deployment settings for the icon solver.

Everything a downstream fork is expected to touch lives here: where the model
is hosted, how detections are thresholded, and the class tables.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir

# Where the model is hosted. `HF_ENDPOINT` is the same variable huggingface_hub
# reads, so pointing it at a mirror (https://hf-mirror.com) reroutes this too.
FILENAME = 'icon_t1_261010'
OWNER = 'wulu007'
HF_REPO = 'gt'
DEFAULT_ENDPOINT = 'https://huggingface.co'

CACHE_DIR = Path(user_cache_dir('wulu-geetest-bypass', appauthor=False))
MODEL_PATH = CACHE_DIR / FILENAME


def model_url() -> str:
    """Read the endpoint at call time, so ``HF_ENDPOINT`` may be set after import."""
    endpoint = os.environ.get('HF_ENDPOINT', DEFAULT_ENDPOINT).rstrip('/')
    return f'{endpoint}/{OWNER}/{HF_REPO}/resolve/main/{FILENAME}'


CONF_THRES = float(os.environ.get('WULU_ICON_CONF_THRES', 0.10))
IOU_THRES = float(os.environ.get('WULU_ICON_IOU_THRES', 0.45))
MAX_DET = int(os.environ.get('WULU_ICON_MAX_DET', 4))

# Direction-type question icons are fixed CDN assets whose filename equals the
# MD5 of their bytes. Hashing the question bytes recovers the arrow's direction
# without any image comparison. Keys: md5 hex; values: direction.
DIR_HASHES = {
    '8da090c135ff029f3b5e19f4c44f73c8': 'u',
    'cb0eaa639b2117a69a81af3d8c1496a1': 'd',
    '315ce8665e781dabcd1eb09d3e604803': 'l',
    '38bd9dda695098c7dfad74c921923a7d': 'lu',
    '502e51dbabf411beba2dcd55fd38ebbd': 'ld',
    '2b2387f566f6a03ed594d4d7cfda471f': 'r',
    '78dc29045d587ad054c7353732df53c5': 'ru',
    '23ef93e6b0e0df0e15b66667c99a5fb4': 'rd',
}

# Fallback channel order, used only when the model carries no ``names``
# metadata. ``WULU_ICON_DIRECTIONS`` (comma-separated) overrides it.
DIR_NAMES = os.environ.get('WULU_ICON_DIRECTIONS', 'u,d,l,r,lu,ld,ru,rd').split(',')
