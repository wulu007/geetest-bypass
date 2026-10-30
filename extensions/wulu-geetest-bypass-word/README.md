# wulu-geetest-bypass-word

Offline **word**-type (文字点选) solver for Geetest v4 CAPTCHAs. A YOLO model locates the character candidates on the background image, then each prompt character is matched to its candidate by cosine similarity over PP-OCR rec embeddings.

## How it works

The `word` CAPTCHA shows a background image with stylized characters and asks the user to click the target characters in the given order:

1. **YOLO Detection**: the background is letterboxed to the model's own input shape (read from the ONNX graph — `320x320` for the shipped `locate.onnx`) and run through it (single-class head `(4 + 1, anchors)`). Candidate boxes are filtered with confidence + NMS and cropped. The graph's `box_format` metadata decides how the four box channels are read: LibreYOLO exports bake decoding in and emit `(x1, y1, x2, y2)`, Ultralytics exports emit the anchor encoding `(cx, cy, w, h)`. A model that does not declare it is **rejected at load time** — the loader never guesses, because reading `xyxy` as `cxcywh` produces plausible-looking but wrong boxes instead of an error. `$WORD_BOX_FORMAT` is the manual escape hatch for models you cannot re-export.
2. **Posterior features** (PP-OCRv6 small rec, run with plain `onnxruntime`): each crop and each prompt thumbnail is fed at `max_wh_ratio = max(2.0, widest in batch)` — 96px wide instead of PaddleOCR's 320px floor — producing a CTC posterior over the whole character dictionary (`[T=12, 18710]`). Everything a plain `recognize_txt` throws away — the ranking over near-miss characters — is what makes two renderings of the same glyph separable. Preprocessing mirrors `RecResizeImg` exactly: resize to the graph's 48px height, pad on the right with zeros in normalised space (pixel 127.5, mid-grey) — the fill the model was trained with. Narrowing the floor only trims the wasted frames (measured identical accuracy, 2.9x less time in this stage).
3. **Masked pooling**: a 48px-wide glyph only occupies the first `48 / 8 = 6` of the `T = 12` time steps. Averaging the padding steps in dilutes every feature towards the shared "blank" direction, so only the valid frames are averaged.
4. **Centering**: the residual shared direction still pins all pair similarities to ~0.999. Subtracting the mean of the challenge's own feature vectors (3 prompt thumbnails + N candidates) removes it, widening the correct-vs-wrong margin from ~1e-4 to ~0.3.
5. **Assignment**: cosine matrix → global optimal assignment minimizing total distance → normalized `(x, y)` centers in `[0.0, 1.0]`.

## Models

- `locate.onnx` (~8.3 MB): character detector, shared with the phrase extension (input `[1, 3, 320, 320]`, output `[1, 5, 2100]` — anchors × `x1, y1, x2, y2, score`, see `box_format` above).
- `ppocrv6_small_rec.onnx` (~21 MB): recogniser, fetched from `PaddlePaddle/PP-OCRv6_small_rec_onnx`. Only its CTC posterior is used, so the character dictionary is not needed — no OCR framework is involved, just `onnxruntime`.

### Lookup Order

| Asset | Environment variable | Local path | Fallback |
| --- | --- | --- | --- |
| detector | `$WORD_YOLO_MODEL_PATH` (or `$WORD_BOX_FORMAT` to force `xyxy` / `cxcywh`) | `repo/gt/yolo-text/261028/locate.onnx` | Pooch → `wulu007/gt` (`yolo-text/261028`) |
| recogniser | `$WORD_REC_MODEL_PATH` | — | Pooch → `PaddlePaddle/PP-OCRv6_small_rec_onnx` |

Downloads respect `$HF_TOKEN` and `$HF_ENDPOINT` and are SHA256-pinned.

Prefetch assets via CLI:

```bash
gt-pull download word
```

## Usage

```python
from wulu_geetest_bypass import Geetest

gt = Geetest(captcha_id='...', risk_type='word')
# Solved automatically via plugin discovery
```

Lower-level access:

```python
import cv2
import numpy as np

from wulu_geetest_bypass_word import detect_candidates, match_chars, solve_word

img = cv2.imdecode(np.frombuffer(imgs, np.uint8), cv2.IMREAD_COLOR)
boxes = detect_candidates(img)  # [[x, y, w, h], ...]
crops = [img[y : y + h, x : x + w] for x, y, w, h in boxes]
indices = match_chars(ques, crops)  # one candidate index per prompt character
clicks = solve_word(imgs, ques)
```

## Accuracy

On 64 hand-labelled challenges (boxes taken from the labels, so detection is not a factor):

| Matching | Per-character | Whole challenge (3/3) |
| --- | --- | --- |
| hard argmax + string equality (what `recognize_txt` gives you) | 88.5% | 67.2% |
| pooled posterior, plain cosine | 97.9% | 96.9% |
| **masked + centered cosine** | **99.0%** | **98.4%** |

The remaining failure is a confidently misread near-synonym glyph (`薏` read as `慧`) — the posterior ranks it top with a wide margin, so no confidence threshold can flag it.

## License

This package is MIT — see `LICENSE`. The recogniser it downloads is
PaddlePaddle's PP-OCRv6 small rec, **Apache-2.0** per the upstream PaddleOCR
repository; it is fetched at runtime and never redistributed here.

`NOTICE` is the authoritative attribution for this package and ships inside the
wheel (`License-File: NOTICE`), since the package is published on its own. The
repository's `THIRD_PARTY_NOTICES.md` only indexes which workspace member owns
which notice.
