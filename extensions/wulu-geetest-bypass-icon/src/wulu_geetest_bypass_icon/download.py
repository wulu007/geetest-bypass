from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from ._config import CACHE_DIR, MODEL_PATH, SOURCES


def resolve_model():
    env = os.environ.get('WULU_ICON_MODEL')
    if env and Path(env).is_file():
        return Path(env)
    if MODEL_PATH.is_file():
        return MODEL_PATH
    return download_model()


def download_model() -> Path:
    """Download the onnx model into the cache dir.

    Sources are tried in order (HuggingFace, then GitHub Release) until one
    succeeds. The payload is written to a temp file next to the target and
    atomically renamed, so a partial or failed download never leaves a bogus
    model behind. Returns the cache path.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for name, url in SOURCES:
        try:
            _download_to(url, MODEL_PATH)
            return MODEL_PATH
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f'{name}: {exc}')
    raise RuntimeError('icon: no download source available: ' + ' | '.join(errors))


def _download_to(url: str, target: Path) -> None:
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=target.name + '.',
            suffix='.part',
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            with urllib.request.urlopen(url, timeout=60) as resp:
                shutil.copyfileobj(resp, tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        if tmp_name:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
        raise
