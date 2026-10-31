"""Voice 数据准备（旧流程，训练已迁走）。

训练请用 `scripts/voice/train.py`：它按音色版本打包到 `weights/<version>.npz`，
本脚本原来的 `train` 会写 `{lang}.npz` 到包目录，新 solver 已不再读取。

Usage:
  uv run python scripts/build_voice_templates.py fetch      <lang>  # 下载20个样本
  uv run python scripts/build_voice_templates.py transcribe <lang>  # Whisper 转写（一次）
  uv run python scripts/build_voice_templates.py verify     <lang>  # 分割验证（不用模型）
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from faster_whisper import WhisperModel
from wulu_geetest_bypass_voice.solver import (
    _load_audio,
    _split_by_silence,
)

from wulu_geetest_bypass import Geetest

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'
RAW_DIR = Path('resources/voice/raw')
TRANS_DIR = Path('resources/voice/transcripts')
SR = 16000

from voice.digits import WHISPER_LANG, WORD_MAP, extract  # noqa: E402


async def fetch(lang: str):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    _seen, count = set(), 0
    while count < 20:
        # pyrefly: ignore [bad-argument-type]
        g = Geetest(captcha_id=CAPTCHA_ID, lang=lang, voice=True)
        data = await g.load()
        mp3 = await g._load_resource(data['voice_path'])
        fname = lang + '_' + str(count) + '_' + data['voice_path'].split('/')[-1]
        path = RAW_DIR / fname
        if path.exists():
            continue
        path.write_bytes(mp3)
        count += 1
        print('[' + str(count) + '/20] ' + fname)
    print('Done fetching ' + lang)


def _common_prefix(texts: list[str]) -> str:
    if not texts:
        return ''
    prefix = texts[0].lower()
    for t in texts[1:]:
        t_lower = t.lower()
        while not t_lower.startswith(prefix) and prefix:
            prefix = prefix[:-1]
        if not prefix:
            break
    return prefix.strip()


def _transcribe_one(path: Path, whisper, wlang: str, kw: dict) -> str:
    segs_w, _ = whisper.transcribe(str(path), **kw)
    return ''.join(s.text for s in segs_w)


def transcribe(lang: str):
    model_name = os.environ.get('WHISPER_MODEL', 'small')
    cpu_threads = int(os.environ.get('WHISPER_CPU_THREADS', '4'))
    whisper = WhisperModel(
        model_name,
        device='cpu',
        compute_type='int8',
        cpu_threads=cpu_threads,
    )
    files = sorted(RAW_DIR.glob(lang + '_*'))
    wm = WORD_MAP.get(lang, {})
    wlang = WHISPER_LANG.get(lang, 'zh')
    kw = {
        'language': wlang,
        'beam_size': 5,
        'vad_filter': True,
        'condition_on_previous_text': False,
    }
    if lang == 'jpn':
        kw['initial_prompt'] = '0 1 2 3 4 5 6 7 8 9'

    results = []
    print(f'开始识别 {len(files)} 个文件...')
    for i, path in enumerate(files):
        text = _transcribe_one(path, whisper, wlang, kw)
        results.append({'file': path.name, 'whisper': text})
        print(f'[{i + 1}/{len(files)}] {path.name} -> {text[:60]}')

    prefix = _common_prefix([r['whisper'] for r in results])
    prefix_lower = prefix.lower()
    print(f'检测到公共前缀: {prefix!r}')

    for r in results:
        text = r['whisper']
        if prefix_lower and text.lower().startswith(prefix_lower):
            text = text[len(prefix) :].lstrip('.,!?;: ')
        if lang == 'jpn':
            for particle in ('を入力', '入力', 'お'):
                if text.startswith(particle):
                    text = text[len(particle) :].lstrip('.,!?;: ')
                    break
        r['digits'] = extract(text, wm)
        print(r['file'] + ' 最终提取 -> ' + (r['digits'] if r['digits'] else '(empty)'))

    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(TRANS_DIR / (lang + '.json')), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print('Saved ' + lang + '.json')


def verify(lang: str):
    trans_path = TRANS_DIR / (lang + '.json')
    if not trans_path.exists():
        print('No transcript found, run transcribe first')
        return

    with open(str(trans_path)) as f:
        trans = json.load(f)

    digit_count = {}
    seg_ok, seg_total = 0, 0

    for r in trans:
        path = RAW_DIR / r['file']
        if not path.exists():
            continue
        mp3 = path.read_bytes()
        y = _load_audio(mp3, SR)
        segs = _split_by_silence(y, SR)
        seg_total += 1
        seg_ok_flag = len(segs) == 7
        if seg_ok_flag:
            seg_ok += 1

        has_6 = len(r['digits']) == 6
        for c in r['digits']:
            digit_count[c] = digit_count.get(c, 0) + 1
        r['segments'] = len(segs)
        r['seg_ok'] = seg_ok_flag
        r['digits_ok'] = has_6

    with open(str(trans_path), 'w', encoding='utf-8') as f:
        json.dump(trans, f, ensure_ascii=False, indent=2)

    covered = [str(i) for i in range(10) if digit_count.get(str(i), 0) > 0]
    valid = [r for r in trans if r['digits_ok'] and r['seg_ok']]
    w_ok = len([r for r in trans if r['digits_ok']])

    print()
    print('=== ' + lang + ' ===')
    print('whisper: ' + str(w_ok) + '/20 OK')
    print('seg:     ' + str(seg_ok) + '/' + str(seg_total) + ' OK')
    print('both:    ' + str(len(valid)) + '/20 OK')
    print(
        'cover:   '
        + str(len(covered))
        + '/10  missing='
        + str(set('0123456789') - set(covered))
    )
    print()

    for r in trans:
        d = r['digits'] if r['digits'] else '(empty)'
        seg_label = 'OK' if r['seg_ok'] else 'FAIL(' + str(r['segments']) + ')'
        ok_label = 'OK' if r['digits_ok'] else 'SKIP'
        w = r['whisper'][:60]
        print(
            '  '
            + r['file'][:50].rjust(50)
            + '  '
            + ok_label.rjust(4)
            + '  seg='
            + seg_label
            + '  '
            + d
            + '  '
            + w
        )


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd, lang = sys.argv[1], sys.argv[2]
    if cmd == 'fetch':
        asyncio.run(fetch(lang))
    elif cmd == 'transcribe':
        transcribe(lang)
    elif cmd == 'verify':
        verify(lang)
    elif cmd == 'train':
        print('train 已迁移到 scripts/voice/train.py（按音色版本打包到 weights/）')
    else:
        print('Unknown command: ' + cmd)
        print(__doc__)


if __name__ == '__main__':
    main()
