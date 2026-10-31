import base64
import copy
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
    'svg_seed',
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
    'svg_seed': 'SVG 图像点选',
    'svg_icon': 'SVG 矢量点选',
}


@pytest.fixture
def bench_record():
    """测试用例记录基准测试数据的 fixture。"""

    def _record(
        name: str,
        display_name: str,
        samples: int,
        passed: int,
        solver_times: Sequence[float],
        e2e_times: Sequence[float] | None = None,
    ) -> None:
        _BENCHMARK_RECORDS[name] = {
            'name': name,
            'display_name': display_name,
            'samples': samples,
            'passed': passed,
            'pass_rate': (passed / samples * 100) if samples else 0.0,
            'retry_pass_rate': ((1.0 - ((samples - passed) / samples) ** 2) * 100.0)
            if samples
            else 0.0,
            # 线上真实题目、verify 之后单次计时；与 pytest-benchmark 的热数据分开存放
            'solver_live_times': [round(t, 2) for t in solver_times],
            # 线上采样完成时间；各题型分批测试，不能共用一个全局时间
            'tested_at': time.strftime('%Y-%m-%d'),
            'e2e_times': [round(t, 2) for t in e2e_times]
            if e2e_times is not None
            else [],
        }

    return _record


def _dump_failure(
    root: Path,
    name: str,
    index: int,
    raw: dict,
    data: dict,
    resp: dict,
) -> Path:
    """落盘失败题的 load 原始数据与已加载资源，便于离线复现。

    `raw` 是 `load()` 的原样返回（`verify` 会就地改写 `data`）；`data` 是加载后的，
    里面的 bytes / svg 文本单独存文件，`load.json` 只保留接口字段。
    """
    lot = str(raw.get('lot_number', index))
    case = root / 'solver_debug' / name / 'failed' / f'{index:02d}_{lot}'
    case.mkdir(parents=True, exist_ok=True)

    (case / 'load.json').write_text(
        json.dumps(raw, ensure_ascii=False, indent=2, default=str), encoding='utf-8'
    )

    assets = {}
    for key, value in data.items():
        if isinstance(value, bytes):
            ext = '.png' if value[:4] == b'\x89PNG' else '.bin'
            (case / f'{key}{ext}').write_bytes(value)
            assets[key] = f'{key}{ext}'
        elif isinstance(value, str) and value.lstrip().startswith('<svg'):
            (case / f'{key}.svg').write_text(value, encoding='utf-8')
            assets[key] = f'{key}.svg'
        elif isinstance(value, str) and value.startswith('iVBOR'):
            (case / f'{key}.png').write_bytes(base64.b64decode(value))
            assets[key] = f'{key}.png'
        elif isinstance(value, list) and value and isinstance(value[0], bytes):
            for i, blob in enumerate(value):
                ext = '.png' if blob[:4] == b'\x89PNG' else '.bin'
                (case / f'{key}_{i}{ext}').write_bytes(blob)
            assets[key] = f'{key}_0..{len(value) - 1}'

    (case / 'verify.json').write_text(
        json.dumps(
            {'assets': assets, 'response': resp},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding='utf-8',
    )
    return case


@pytest.fixture
def pass_rate(cid, bench_record, out_dir):
    """跑某题型的线上首猜通过率，结果写进基准数据；返回 ``(通过, 提交)``。

    ``solve`` 是本地求解器（可选）：传了就在 ``verify`` 之外单独计时，供报告里的算法耗时列用；
    不传则只有端到端耗时。``forbidden`` 是 IP 级拒绝、没进打分，不计入分母。
    失败的题会把 ``load`` 原始数据与资源归档到 ``resources/solver_debug/<题型>/failed/``，
    ``on_fail(data, case_dir)`` 可追加题型自己的现场图（如 word 的候选框标注），
    ``WULU_FAIL_DUMP=0`` 可关闭归档。
    """

    async def _run(
        risk_type: str,
        floor: float,
        solve=None,
        *,
        samples: int | None = None,
        captcha_id: str | None = None,
        record_as: str | None = None,
        on_fail=None,
        **options,
    ) -> tuple[int, int]:
        import asyncio

        from wulu_geetest_bypass import Geetest
        from wulu_geetest_bypass._exceptions import RateLimitError

        name = record_as or risk_type
        tag = name.upper()
        total = samples or int(os.environ.get(f'WULU_{tag}_PASS_SAMPLES', '50'))
        floor = float(os.environ.get(f'WULU_{tag}_MIN_RATE', floor))
        # pyrefly: ignore[bad-argument-type]
        g = Geetest(captcha_id=captcha_id or cid, risk_type=risk_type, **options)

        hit = attempted = blocked = 0
        streak = 0
        dump = os.environ.get('WULU_FAIL_DUMP', '1') != '0'
        failed_dirs: list[Path] = []
        solver_times: list[float] = []
        e2e_times: list[float] = []
        while attempted < total:
            t0 = time.perf_counter()
            data = await g.load()
            raw = copy.deepcopy(data)  # verify 会就地改写 data，先留一份原样
            try:
                resp = await g.verify(data)
            except RateLimitError:
                print(f'{name}(accuracy): 限流，退避 5s', flush=True)
                await asyncio.sleep(5.0)
                continue
            except Exception as e:  # noqa: BLE001
                streak += 1
                print(f'{name}(accuracy): {type(e).__name__}: {e}', flush=True)
                if streak >= 3:
                    print(f'{name}(accuracy): 连续 3 次出错，提前结束', flush=True)
                    break
                continue
            streak = 0
            e2e = (time.perf_counter() - t0) * 1000

            result = resp['data']['result']
            if result == 'forbidden':
                blocked += 1
                print(f'{name}(accuracy): forbidden 第 {blocked} 次', flush=True)
                if blocked >= 3:
                    print(f'{name}(accuracy): 连续风控，提前结束', flush=True)
                    break
                await asyncio.sleep(30.0)
                continue

            attempted += 1
            hit += result == 'success'
            e2e_times.append(e2e)
            if result != 'success' and dump:
                # pyrefly: ignore[bad-argument-type]
                case = _dump_failure(out_dir, name, attempted, raw, data, resp)
                failed_dirs.append(case)
                if on_fail is not None:
                    try:
                        on_fail(data, case)
                    except Exception as e:  # noqa: BLE001
                        print(f'{name}(accuracy): 失败回调出错 {e}', flush=True)
            # verify 内部才把图片/音频下载到 data 里，所以求解器只能在这之后单独计时
            if solve is not None:
                try:
                    t1 = time.perf_counter()
                    solve(data)
                    solver_times.append((time.perf_counter() - t1) * 1000)
                except Exception as e:  # noqa: BLE001
                    print(f'{name}(accuracy): 求解器二次调用失败 {e}', flush=True)
            print(f'{name}(accuracy): {attempted:>3d}/{total} {result}', flush=True)
            await asyncio.sleep(0.5)

        assert attempted, '一题都没提交成功（全被风控或限流）'
        bench_record(
            name,
            _DISPLAY_NAMES[name],
            attempted,
            hit,
            solver_times,
            e2e_times,
        )
        rate = hit / attempted
        print(
            f'\n{name}(accuracy): 首猜通过 {hit}/{attempted} = {rate:.1%}',
            flush=True,
        )
        if failed_dirs:
            print(
                f'{name}(accuracy): {len(failed_dirs)} 个失败样本已归档到 '
                f'{out_dir / "solver_debug" / name / "failed"}',
                flush=True,
            )
        assert rate >= floor, f'通过率 {rate:.1%} 低于下限 {floor:.0%}'
        return hit, attempted

    return _run


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
    for name, rec in _BENCHMARK_RECORDS.items():
        old = records.get(name, {})
        # 本次没跑 perf 时，保留上次的离线 benchmark 数据
        rec.setdefault('solver_bench_times', old.get('solver_bench_times', []))
        if 'bench_tested_at' in old:
            rec.setdefault('bench_tested_at', old['bench_tested_at'])
        records[name] = rec

    # 合并 pytest-benchmark 的热数据：只认测试里显式声明的 extra_info['type']，
    # 不再靠测试名子串猜题型（子步骤 / 改名都会串台）
    for b in bench_items:
        matched_type = (getattr(b, 'extra_info', None) or {}).get('type')
        raw_data = getattr(getattr(b, 'stats', None), 'data', None)
        if matched_type not in _KNOWN_TYPES or not raw_data:
            continue
        timings = [round(t * 1000, 2) for t in raw_data]
        rec = records.setdefault(
            matched_type,
            {
                'name': matched_type,
                'display_name': _DISPLAY_NAMES.get(matched_type, matched_type),
                'samples': 0,
                'passed': 0,
                'pass_rate': 0.0,
                'retry_pass_rate': 0.0,
                'solver_live_times': [],
                'e2e_times': [],
            },
        )
        rec['solver_bench_times'] = timings
        rec['bench_tested_at'] = time.strftime('%Y-%m-%d')

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
            'tested_at': time.strftime('%Y-%m-%d'),
        },
        'records': records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    print(f'\n[benchmark] 数据已保存到: {out_path} (共 {len(records)} 个题型)')
