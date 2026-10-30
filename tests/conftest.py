import functools
import json
import os
import platform
import time
from collections.abc import Sequence
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


# --- 基准测试指标自动收集 ----------------------------------------------------

_BENCHMARK_RECORDS: dict[str, dict] = {}

_KNOWN_TYPES = (
    'slide',
    'voice',
    'icon',
    'phrase',
    'nine',
    'word',
    'match',
    'winlinze',
    'svg_icon',
)

_DISPLAY_NAMES = {
    'slide': '滑块拼图',
    'voice': '语音验证码',
    'icon': '图标方向点选',
    'phrase': '语序点选',
    'nine': '九宫格点选',
    'word': '文字点选',
    'match': '空间匹配',
    'winlinze': '阴阳五行',
    'svg_icon': 'SVG 矢量点选',
}

_ENGINES = {
    'slide': 'OpenCV 模板匹配',
    'voice': '离线 MFCC 特征',
    'icon': 'YOLO + 方向比对',
    'phrase': 'YOLO + RapidOCR',
    'nine': 'ConvNeXt 图像分类',
    'word': 'YOLO + PP-OCR 特征',
    'match': '纯算法匹配',
    'winlinze': '纯算法匹配',
    'svg_icon': 'resvg + Pillow',
}


@pytest.fixture
def bench_record():
    """测试用例记录基准测试数据的 fixture。"""

    def _record(
        name: str,
        display_name: str,
        engine: str,
        samples: int,
        passed: int,
        solver_times: Sequence[float],
        e2e_times: Sequence[float] | None = None,
    ) -> None:
        _BENCHMARK_RECORDS[name] = {
            'name': name,
            'display_name': display_name,
            'engine': engine,
            'samples': samples,
            'passed': passed,
            'pass_rate': (passed / samples * 100) if samples else 0.0,
            'retry_pass_rate': ((1.0 - ((samples - passed) / samples) ** 2) * 100.0)
            if samples
            else 0.0,
            'solver_times': [round(t, 2) for t in solver_times],
            'e2e_times': [round(t, 2) for t in e2e_times]
            if e2e_times is not None
            else [],
        }

    return _record


def pytest_sessionfinish(session):
    bs = getattr(session.config, '_benchmarksession', None)
    bench_items = getattr(bs, 'benchmarks', []) if bs else []

    if not _BENCHMARK_RECORDS and not bench_items:
        return

    out_path = Path(__file__).resolve().parents[1] / 'resources' / 'benchmark_data.json'
    existing: dict = {}
    if out_path.is_file():
        try:
            existing = json.loads(out_path.read_text(encoding='utf-8'))
        except Exception:
            existing = {}

    records = existing.get('records', {})
    records.update(_BENCHMARK_RECORDS)

    # 自动合并来自 pytest-benchmark 的高精度耗时
    for b in bench_items:
        name = getattr(b, 'name', '') or ''
        matched_type = next((t for t in _KNOWN_TYPES if t in name.lower()), None)
        if not matched_type:
            continue
        stats = getattr(b, 'stats', None)
        raw_data = getattr(stats, 'data', None)
        if not raw_data:
            continue
        timings = [round(t * 1000, 2) for t in raw_data]
        if matched_type not in records:
            records[matched_type] = {
                'name': matched_type,
                'display_name': _DISPLAY_NAMES.get(matched_type, matched_type),
                'engine': _ENGINES.get(matched_type, '-'),
                'samples': 0,
                'passed': 0,
                'pass_rate': 0.0,
                'retry_pass_rate': 0.0,
                'solver_times': timings,
                'e2e_times': [],
            }
        else:
            records[matched_type]['solver_times'] = timings

    mach = bs.get_machine_info() if bs else {}
    cpu_info = mach.get('cpu') or {}
    cpu_model = (
        cpu_info.get('brand_raw')
        or mach.get('processor')
        or platform.processor()
        or 'Unknown CPU'
    )
    cpu_cores = cpu_info.get('count') or os.cpu_count() or 1
    os_name = (
        f'{mach.get("system", "")} {mach.get("release", "")}'.strip()
        or platform.platform()
    )
    python_version = mach.get('python_version') or platform.python_version()

    data = {
        'env': {
            'cpu_model': cpu_model,
            'cpu_cores': cpu_cores,
            'os_name': os_name,
            'python_version': python_version,
            'tested_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        },
        'records': records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    print(f'\n[benchmark] 数据已保存到: {out_path} (共 {len(records)} 个题型)')
