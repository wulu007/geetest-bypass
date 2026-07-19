"""Dev-only: build voice digit centroids + prompt templates.
Requires: uv add --dev faster-whisper"""

import asyncio
import sys
import tempfile

import numpy as np
from faster_whisper import WhisperModel

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.solver.voice import (
    _load_audio,
    _mfcc_feature,
    _split_by_silence,
)

CAPTCHA_ID = '54088bb07d2df3c46b79f80300b0abbe'

CN_NUM = {
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
}

EN_NUM = {
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
}


def extract_digits_en(text: str) -> list[str]:
    words = text.lower().split()
    digits = []
    for w in words:
        w = w.strip('.,!?;:')
        if w in EN_NUM:
            digits.append(EN_NUM[w])
        elif w.isdigit():
            digits.extend(list(w))
    return digits[-6:] if len(digits) >= 6 else digits


def extract_digits_zh(text: str) -> list[str]:
    digits = []
    for c in text:
        if c in CN_NUM:
            digits.append(CN_NUM[c])
        elif c.isdigit():
            digits.append(c)
    return digits[-6:] if len(digits) >= 6 else digits


EXTRACTORS = {'zh': extract_digits_zh, 'eng': extract_digits_en}

SR = 16000


async def collect_samples(n: int, lang: str) -> tuple:
    whisper = WhisperModel('small', device='cpu', compute_type='int8')
    extract = EXTRACTORS[lang]
    all_digit_feats, all_labels = [], []
    all_prompt_feats = []

    for idx in range(n):
        g = Geetest(captcha_id=CAPTCHA_ID, risk_type='ai', voice=True, lang=lang)
        data = await g.load()
        mp3 = await g._load_resource(data['voice_path'])

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(mp3)
            path = f.name

        whisper_lang = {'eng': 'en'}.get(lang, lang)
        segments, _ = whisper.transcribe(path, language=whisper_lang, beam_size=1)
        text = ''.join(s.text for s in segments)
        digits = extract(text)
        if len(digits) != 6:
            print(f'[{idx}] skip: {text!r} -> {digits}')
            continue

        with open(path, 'rb') as fh:
            y = _load_audio(fh.read(), SR)
        segs = _split_by_silence(y, SR)
        if len(segs) < 7:
            print(f'[{idx}] skip: {len(segs)} segments')
            continue

        prompt_feat = _mfcc_feature(segs[0], SR)
        all_prompt_feats.append(prompt_feat)

        for seg, d in zip(segs[1 : 1 + 6], digits):
            all_digit_feats.append(_mfcc_feature(seg, SR))
            all_labels.append(int(d))

        print(f'[{idx}] collected: {"".join(digits)}')

    return np.array(all_digit_feats), np.array(all_labels), np.array(all_prompt_feats)


def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else 'zh'
    print(f'Building templates for lang={lang}')

    digit_feats, labels, prompt_feats = asyncio.run(collect_samples(20, lang))

    centroids = np.array([digit_feats[labels == i].mean(axis=0) for i in range(10)])
    digits = np.arange(10)

    correct = 0
    for feat, label in zip(digit_feats, labels):
        dists = np.linalg.norm(centroids - feat, axis=1)
        if digits[dists.argmin()] == label:
            correct += 1
    print(
        f'Accuracy: {correct}/{len(digit_feats)} ({100 * correct / len(digit_feats):.0f}%)'
    )

    prompt_centroid = prompt_feats.mean(axis=0)

    np.savez(
        f'src/wulu_geetest_bypass/templates/voice_templates_{lang}.npz',
        X=centroids.astype(np.float32),
        y=digits,
        sr=SR,
        lang=lang,
        prompt=prompt_centroid.astype(np.float32),
    )
    print(
        f'Saved {lang} templates: centroids={centroids.shape} prompt={prompt_centroid.shape}'
    )


if __name__ == '__main__':
    main()
