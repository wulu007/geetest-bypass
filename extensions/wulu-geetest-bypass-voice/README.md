# wulu-geetest-bypass-voice

Voice digit recognition templates for [wulu-geetest-bypass](https://github.com/wulu007/geetest-bypass).

> **Note**: This is an extension package for `wulu-geetest-bypass` and is not intended for standalone use. Install via the main package instead.

Provides pre-computed MFCC centroids for 12 languages, enabling offline digit recognition in Geetest v4 voice captchas without any deep learning framework.

## Installation

```bash
pip install wulu-geetest-bypass[voice]
```

## Supported Languages

| Code | Language |
|------|----------|
| ara | Arabic |
| deu | German |
| eng | English |
| fra | French |
| ind | Indonesian |
| jpn | Japanese |
| kor | Korean |
| por | Portuguese |
| rus | Russian |
| spa | Spanish |
| zho | Chinese (Mandarin) |
| zho-hk | Chinese (Cantonese) |

## Usage

```python
from wulu_geetest_bypass_voice import load_templates

X, y, sr, lang, prompt = load_templates('eng')
# X: (10, 39) centroid array
# y: [0 1 2 3 4 5 6 7 8 9]
# sr: 16000
# lang: 'eng'
# prompt: (39,) prompt centroid
```