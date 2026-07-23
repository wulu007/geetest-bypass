"""Voice template builder.
Usage:
  uv run python scripts/build_voice_templates.py fetch   <lang>  # 下载20个样本
  uv run python scripts/build_voice_templates.py verify  <lang>  # Whisper + 分割验证
  uv run python scripts/build_voice_templates.py train   <lang>  # 训练模板
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.solver.voice import (
    _load_audio,
    _mfcc_feature,
    _split_by_silence,
)

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'
RAW_DIR = Path('resources/voice/raw')
TRANS_DIR = Path('resources/voice/transcripts')
OUT_DIR = Path('extensions/wulu-geetest-bypass-voice/src/wulu_geetest_bypass_voice')
SR = 16000

WHISPER_LANG = {
    'zho': 'zh',
    'eng': 'en',
    'jpn': 'ja',
    'ind': 'id',
    'kor': 'ko',
    'rus': 'ru',
    'ara': 'ar',
    'spa': 'es',
    'fra': 'fr',
    'deu': 'de',
    'zho-hk': 'yue',
    'por': 'pt',
}

WORD_MAP = {
    'zho': {
        '零': '0',
        '一': '1',
        '二': '2',
        '三': '3',
        '四': '4',
        '五': '5',
        '六': '6',
        '七': '7',
        '八': '8',
        '九': '9',
        '幺': '1',
        '两': '2',
    },
    'zho-hk': {
        '零': '0',
        '一': '1',
        '二': '2',
        '三': '3',
        '四': '4',
        '五': '5',
        '六': '6',
        '七': '7',
        '八': '8',
        '九': '9',
        '幺': '1',
        '两': '2',
    },
    'eng': {
        'zero': '0',
        'one': '1',
        'two': '2',
        'three': '3',
        'four': '4',
        'five': '5',
        'six': '6',
        'seven': '7',
        'eight': '8',
        'nine': '9',
        'oh': '0',
    },
    'deu': {
        'null': '0',
        'eins': '1',
        'ein': '1',
        'zwei': '2',
        'drei': '3',
        'vier': '4',
        'fuenf': '5',
        'fünf': '5',
        'sechs': '6',
        'sieben': '7',
        'acht': '8',
        'neun': '9',
    },
    'fra': {
        'zero': '0',
        'un': '1',
        'deux': '2',
        'trois': '3',
        'quatre': '4',
        'cinq': '5',
        'six': '6',
        'sept': '7',
        'huit': '8',
        'neuf': '9',
    },
    'rus': {
        'ноль': '0',
        'один': '1',
        'раз': '1',
        'два': '2',
        'три': '3',
        'четыре': '4',
        'пять': '5',
        'шесть': '6',
        'семь': '7',
        'восемь': '8',
        'девять': '9',
    },
    'jpn': {
        'zero': '0',
        'rei': '0',
        'いち': '1',
        'に': '2',
        'さん': '3',
        'よん': '4',
        'し': '4',
        'ご': '5',
        'ろく': '6',
        'なな': '7',
        'しち': '7',
        'はち': '8',
        'きゅう': '9',
        'く': '9',
    },
    'kor': {
        'yeong': '0',
        'gong': '0',
        'il': '1',
        'i': '2',
        'sam': '3',
        'sa': '4',
        'o': '5',
        'yuk': '6',
        'chil': '7',
        'pal': '8',
        'gu': '9',
    },
    'ara': {
        'sifr': '0',
        'wahid': '1',
        'ithnan': '2',
        'thalatha': '3',
        'arbaa': '4',
        'khamsa': '5',
        'sitta': '6',
        'sabaa': '7',
        'thamania': '8',
        'tissa': '9',
    },
    'spa': {
        'cero': '0',
        'uno': '1',
        'dos': '2',
        'tres': '3',
        'cuatro': '4',
        'cinco': '5',
        'seis': '6',
        'siete': '7',
        'ocho': '8',
        'nueve': '9',
    },
    'por': {
        'zero': '0',
        'um': '1',
        'dois': '2',
        'tres': '3',
        'quatro': '4',
        'cinco': '5',
        'seis': '6',
        'sete': '7',
        'oito': '8',
        'nove': '9',
    },
}

_re_digit = re.compile(r'\d')


_PROMPTS = {
    'deu': 'geben sie ein,',
    'fra': 'veuillez saisir ce que vous entendez',
    'rus': 'vidite to, chto slyshite',
    'eng': 'enter what you hear',
}


def extract(text: str, lang: str) -> str:
    prompt = _PROMPTS.get(lang)
    if prompt:
        text = text.lower()
        idx = text.find(prompt)
        if idx >= 0:
            text = text[idx + len(prompt) :].lstrip('.,!?;: ')
    digits = []
    wm = WORD_MAP.get(lang, {})
    for token in text.lower().split():
        token = token.strip('.,!?;:')
        if token.isdigit():
            digits.extend(token)
        elif token in wm:
            digits.append(wm[token])
        if len(digits) >= 6:
            break
    return ''.join(digits[-6:])


async def fetch(lang: str):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seen, count = set(), 0
    while count < 20:
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


def verify(lang: str):
    model_name = os.environ.get('WHISPER_MODEL', 'small')
    whisper = WhisperModel(model_name, device='cpu', compute_type='int8')
    wlang = WHISPER_LANG.get(lang, 'zh')
    files = sorted(RAW_DIR.glob(lang + '_*'))
    results = []
    digit_count = {}
    seg_ok, seg_total = 0, 0

    for path in files:
        mp3 = path.read_bytes()
        segs_w, _ = whisper.transcribe(str(path), language=wlang, beam_size=1)
        text = ''.join(s.text for s in segs_w)
        digits = extract(text, lang)

        y = _load_audio(mp3, SR)
        segs = _split_by_silence(y, SR)
        seg_total += 1
        seg_ok_flag = len(segs) == 7
        if seg_ok_flag:
            seg_ok += 1

        has_6 = len(digits) == 6
        for c in digits:
            digit_count[c] = digit_count.get(c, 0) + 1

        results.append(
            {
                'file': path.name,
                'whisper': text.strip(),
                'digits': digits,
                'digits_ok': has_6,
                'segments': len(segs),
                'seg_ok': seg_ok_flag,
            }
        )

    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(TRANS_DIR / (lang + '.json')), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    covered = [str(i) for i in range(10) if digit_count.get(str(i), 0) > 0]
    valid = [r for r in results if r['digits_ok'] and r['seg_ok']]
    w_ok = len([r for r in results if r['digits_ok']])

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

    for r in results:
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


def train(lang: str):
    trans_path = TRANS_DIR / (lang + '.json')
    if not trans_path.exists():
        print('No transcript found, run verify first')
        return

    with open(str(trans_path)) as f:
        results = json.load(f)

    valid = [r for r in results if r['digits_ok'] and r['seg_ok']]
    if len(valid) < 3:
        print('Only ' + str(len(valid)) + ' valid samples, need at least 3')
        return

    all_feats, all_labels, all_prompts = [], [], []
    for r in valid:
        mp3 = (RAW_DIR / r['file']).read_bytes()
        y = _load_audio(mp3, SR)
        segs = _split_by_silence(y, SR)
        all_prompts.append(_mfcc_feature(segs[0], SR))
        for seg, d in zip(segs[1:7], r['digits']):
            all_feats.append(_mfcc_feature(seg, SR))
            all_labels.append(int(d))

    feats = np.array(all_feats)
    labels = np.array(all_labels)
    centroids = np.array([feats[labels == i].mean(axis=0) for i in range(10)])
    digits_arr = np.arange(10)

    correct = sum(
        1
        for f, l in zip(feats, labels)
        if digits_arr[np.linalg.norm(centroids - f, axis=1).argmin()] == l
    )
    acc = correct / len(labels)
    print(
        'Accuracy: '
        + str(correct)
        + '/'
        + str(len(labels))
        + ' ('
        + str(int(100 * acc))
        + '%)'
    )

    if acc < 0.6:
        print('Too low, skip saving')
        return

    prompt = np.array(all_prompts).mean(axis=0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / ('voice_templates_' + lang + '.npz')
    np.savez(
        str(out_path),
        X=centroids.astype(np.float32),
        y=digits_arr,
        sr=SR,
        lang=lang,
        prompt=prompt.astype(np.float32),
    )
    print('Saved to ' + str(out_path))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd, lang = sys.argv[1], sys.argv[2]
    if cmd == 'fetch':
        asyncio.run(fetch(lang))
    elif cmd == 'verify':
        verify(lang)
    elif cmd == 'train':
        train(lang)
    else:
        print('Unknown command: ' + cmd)
        print(__doc__)


if __name__ == '__main__':
    main()
