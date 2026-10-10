# wulu-geetest-bypass-icon

Offline **icon**-type solver for Geetest v4 CAPTCHAs. Locates the background
collage icon that matches each question and returns normalized click
coordinates.

## How it works

The `icon` CAPTCHA shows a collage background built from the same icons that
appear as questions, which makes it a matching problem rather than a
recognition one:

1. The background collage goes through a YOLO model, which returns one box per
   direction icon (`u`, `d`, `l`, `r`, `lu`, `ld`, `ru`, `rd`).
2. Each question thumbnail is MD5-hashed. That digest is the CDN filename of the
   asset, so it maps straight to a direction via `DIR_HASHES` — no image
   comparison involved.
3. The question is answered with the center of the first still-unused detection
   facing that direction.

A question with an unknown MD5, or whose direction has no detection, raises
`UnsupportedQuestionError` instead of guessing.

## Model

The default model is a YOLOv8n ONNX export: input `640x640`, output
`[1, 12, 8400]`, 8 direction classes. It is not trained here — both the ONNX file
and the `DIR_HASHES` table come from
[gaogzhen/GeekedTest](https://github.com/gaogzhen/GeekedTest) under the MIT License.
See [THIRD_PARTY_NOTICES.md](https://github.com/wulu007/geetest-bypass/blob/main/THIRD_PARTY_NOTICES.md).

### Lookup order

1. `$WULU_ICON_MODEL`, if it points at an existing file
2. `<CACHE_DIR>/<FILENAME>`
3. download from `SOURCES` (in order) into `CACHE_DIR`

### Environment variables

| Variable | Meaning | Default |
| --- | --- | --- |
| `WULU_ICON_MODEL` | Path to the ONNX model. Ignored if the file does not exist. | unset → cache, then download |
| `WULU_ICON_DIRECTIONS` | Comma-separated channel order. Used **only** when the model carries no `names` metadata. | `u,d,l,r,lu,ld,ru,rd` |
| `WULU_ICON_CONF_THRES` | Confidence threshold. | `0.10` |
| `WULU_ICON_IOU_THRES` | NMS IoU threshold. | `0.45` |
| `WULU_ICON_MAX_DET` | Max boxes kept per background. | `4` |

### Source constants (`_config.py`)

For downstream forks that ship their own model:

| Constant | Meaning | Default |
| --- | --- | --- |
| `FILENAME` | Model filename; also its name inside the cache dir. | `icon_t1_261010` |
| `OWNER`, `HF_REPO` | HuggingFace repo holding the model. | `wulu007`, `gt` |
| `GH_REPO` | GitHub repo used for the release fallback. | `geetest-bypass` |
| `SOURCES` | Download sources, tried in order. | HuggingFace → GitHub Release |
| `CACHE_DIR` | Where the model is cached. | `platformdirs.user_cache_dir('wulu-geetest-bypass-icon', appauthor=False)` |
| `DIR_HASHES` | Question-icon MD5 → direction. | 8 CDN assets |

### Class order

Read from the model's `names` metadata when present, so a retrained model with a
different class order works with no configuration. Otherwise
`WULU_ICON_DIRECTIONS` (or its default) is used.

Either way the result must be a permutation of the eight known directions, or
the first detection raises `UnsupportedModelError` — as does a model exported
with `end2end=True` (built-in NMS). The output channel count must equal
`4 + len(classes)`; anything else raises too.

## Usage

```bash
uv add wulu-geetest-bypass[icon]
```

The solver registers as an entry point of the `wulu_geetest_bypass.solvers`
group under the `icon` captcha type, and is discovered automatically by
`wulu_geetest_bypass`.

```python
from wulu_geetest_bypass import Geetest

solver = Geetest(captcha_id='your_captcha_id', risk_type='icon')
seccode = await solver.resolve()
```
