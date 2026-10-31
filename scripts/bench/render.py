"""读取 benchmark_data.json 并基于 Jinja2 模板渲染双语性能基准报告。

输出 docs/BENCHMARK.md (English) 与 docs/BENCHMARK.zh-CN.md (简体中文)。

Usage:
    uv run --group bench python scripts/bench/render.py
    uv run --group bench python scripts/bench/render.py --lang en --out docs/BENCHMARK.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from jinja2 import Template

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO / 'resources' / 'benchmark_data.json'
TEMPLATES_DIR = REPO / 'docs' / 'templates'
DOCS_DIR = REPO / 'docs'

# 语言 -> (模板, 输出)；英文为默认，与 README.md / README.zh-CN.md 的命名约定一致
LANGS: dict[str, tuple[Path, Path]] = {
    'en': (TEMPLATES_DIR / 'benchmark.md.j2', DOCS_DIR / 'BENCHMARK.md'),
    'zh-CN': (
        TEMPLATES_DIR / 'benchmark.zh-CN.md.j2',
        DOCS_DIR / 'BENCHMARK.zh-CN.md',
    ),
}

ORDER = [
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
]


def _calc_stats(timings: list[float]) -> dict[str, float]:
    if not timings:
        return {
            'min': 0.0,
            'p50': 0.0,
            'p90': 0.0,
            'p95': 0.0,
            'p99': 0.0,
            'max': 0.0,
        }
    arr = np.asarray(timings, dtype=np.float64)
    return {
        'min': float(np.min(arr)),
        'p50': float(np.percentile(arr, 50)),
        'p90': float(np.percentile(arr, 90)),
        'p95': float(np.percentile(arr, 95)),
        'p99': float(np.percentile(arr, 99)),
        'max': float(np.max(arr)),
    }


# 样本数低于该值时，P99 没有统计意义，报告中不展示
MIN_TAIL_SAMPLES = 100


def _wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """通过率的 Wilson 95% 区间。"""
    if total <= 0:
        return (0.0, 1.0)
    p = hits / total
    denom = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)
    return ((center - margin) / denom, (center + margin) / denom)


def render_benchmark(
    data_path: Path = DEFAULT_DATA,
    template_path: Path = LANGS['en'][0],
    out_path: Path = LANGS['en'][1],
) -> Path:
    if not data_path.is_file():
        raise FileNotFoundError(f'Benchmark data not found: {data_path}')
    if not template_path.is_file():
        raise FileNotFoundError(f'Template not found: {template_path}')

    payload = json.loads(data_path.read_text(encoding='utf-8'))
    records: dict[str, dict] = payload.get('records', {})
    env = payload.get('env', {})

    def sort_key(name: str) -> tuple[int, str]:
        return (ORDER.index(name) if name in ORDER else 999, name)

    types_list = []
    for name in sorted(records.keys(), key=sort_key):
        item = records[name]
        samples = int(item.get('samples', 0))
        passed = int(item.get('passed', 0))
        legacy = item.get('solver_times', [])  # 旧版数据：不区分来源
        live = item.get('solver_live_times', legacy if samples > 0 else [])
        bench = item.get('solver_bench_times', [] if samples > 0 else legacy)
        e2e = item.get('e2e_times', [])
        lo, hi = _wilson(passed, samples)

        types_list.append(
            {
                'name': item.get('name', name),
                'display_name': item.get('display_name', name),
                'samples': samples,
                'tested_at': item.get('tested_at'),
                'bench_tested_at': item.get('bench_tested_at'),
                'pass_rate': item.get('pass_rate', 0.0),
                'ci_low': lo * 100,
                'ci_high': hi * 100,
                'retry_pass_rate': item.get('retry_pass_rate', 0.0),
                'live': _calc_stats(live),
                'live_n': len(live),
                'bench': _calc_stats(bench),
                'bench_n': len(bench),
                'e2e': _calc_stats(e2e),
                'e2e_n': len(e2e),
            }
        )

    template = Template(template_path.read_text(encoding='utf-8'))
    rendered = template.render(types=types_list, env=env, min_tail=MIN_TAIL_SAMPLES)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered.rstrip('\n') + '\n', encoding='utf-8')
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description='Render benchmark report from JSON data.'
    )
    parser.add_argument(
        '--data', type=Path, default=DEFAULT_DATA, help='Path to benchmark_data.json'
    )
    parser.add_argument(
        '--lang',
        choices=[*LANGS, 'all'],
        default='all',
        help='Report language (default: all, rendering every language to docs/)',
    )
    parser.add_argument(
        '--template', type=Path, help='Override template path (needs a single --lang)'
    )
    parser.add_argument(
        '--out', type=Path, help='Override output path (needs a single --lang)'
    )
    args = parser.parse_args()

    langs = list(LANGS) if args.lang == 'all' else [args.lang]
    if (args.template or args.out) and len(langs) != 1:
        parser.error('--template/--out require a single --lang')
    for lang in langs:
        template, out = LANGS[lang]
        out = render_benchmark(args.data, args.template or template, args.out or out)
        print(f'Benchmark report [{lang}] generated -> {out}')


if __name__ == '__main__':
    main()
