import functools
from pathlib import Path

import pytest


@pytest.fixture
def cid() -> str:
    return '54088bb07d2df3c46b79f80300b0abbe'


@pytest.fixture
def out_dir():
    path = Path(__file__).resolve().parents[1] / 'resources'
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def svg_out_dir(out_dir):
    path = out_dir / 'svg'
    path.mkdir(parents=True, exist_ok=True)
    return path


def pytest_collection_modifyitems(config, items):
    known_marks = {'smoke', 'slow', 'integration', 'draw', 'accuracy', 'perf'}
    for item in items:
        if not any(mark.name in known_marks for mark in item.iter_markers()):
            item.add_marker(pytest.mark.unmarked)


# --- 画图用的中文字体 --------------------------------------------------------
# cv2.putText 画不了汉字，得用 PIL + 系统里的中文字体。先试写死的常见路径，
# 再按文件名关键词翻字体目录（覆盖 macOS / Linux 的常见发行版）。

CJK_FONTS = (
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simhei.ttf',
    'C:/Windows/Fonts/simsun.ttc',
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/Library/Fonts/Arial Unicode.ttf',
)
CJK_FONT_DIRS = (
    'C:/Windows/Fonts',
    '/System/Library/Fonts',
    '/Library/Fonts',
    '/usr/share/fonts',
    '/usr/local/share/fonts',
    '~/.local/share/fonts',
)
CJK_NAME_HINTS = (
    'msyh',
    'simhei',
    'simsun',
    'pingfang',
    'hiragino',
    'notosanscjk',
    'notosanssc',
    'sourcehansans',
    'sourcehanserif',
    'wqy',
    'uming',
    'ukai',
    'droidsansfallback',
    'arialuni',
)
_FONT_SUFFIXES = {'.ttc', '.ttf', '.otf'}


@functools.lru_cache(maxsize=1)
def font_path() -> str | None:
    """找一个能画汉字的系统字体；找不到返回 ``None``（PIL 自带字体只有 ASCII）。"""
    for path in CJK_FONTS:
        if Path(path).exists():
            return path
    for directory in CJK_FONT_DIRS:
        base = Path(directory).expanduser()
        if not base.is_dir():
            continue
        files = [f for f in base.rglob('*') if f.suffix.lower() in _FONT_SUFFIXES]
        for hint in CJK_NAME_HINTS:
            hit = next((f for f in files if hint in f.name.lower()), None)
            if hit:
                return str(hit)
    return None


def load_cjk_font(size: int):
    """返回 ``(字体, 能不能画汉字)``；拿不到中文字体时标签只能退化画 ASCII。"""
    from PIL import ImageFont

    path = font_path()
    if path:
        return ImageFont.truetype(path, size), True
    return ImageFont.load_default(size=size), False


@pytest.fixture(scope='session')
def cjk_font():
    return load_cjk_font, font_path()
