from __future__ import annotations

import contextlib
import os
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from ._config import CACHE_DIR, MODEL_PATH, SOURCES

Progress = Callable[[int, int | None], None]


def resolve_model() -> Path:
    env = os.environ.get('WULU_ICON_MODEL')
    if env and Path(env).is_file():
        return Path(env)
    return download_model()


def download_model(progress: Progress | None = None, *, force: bool = False) -> Path:
    """Download the onnx model into the cache dir.

    Returns the cached path without downloading unless ``force`` is set. Sources
    are tried in order (HuggingFace, then GitHub Release) until one succeeds.
    The payload is written to a temp file next to the target and atomically
    renamed, so a partial or failed download never leaves a bogus model behind.
    ``progress`` receives ``(bytes_done, bytes_total | None)``.
    """
    if MODEL_PATH.is_file() and not force:
        return MODEL_PATH
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for name, url in SOURCES:
        try:
            _download_to(url, MODEL_PATH, progress)
            return MODEL_PATH
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f'{name}: {exc}')
    raise RuntimeError('icon: no download source available: ' + ' | '.join(errors))


def _download_to(url: str, target: Path, progress: Progress | None = None) -> None:
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
                total = resp.length
                done = 0
                if progress:
                    progress(done, total)
                while chunk := resp.read(1 << 16):
                    tmp.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        if tmp_name:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
        raise
