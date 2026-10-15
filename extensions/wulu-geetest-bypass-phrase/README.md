# wulu-geetest-bypass-phrase

Offline **phrase**-type solver for Geetest v4 CAPTCHAs. The challenge image shows
four single characters that have to be clicked in the order that spells a phrase;
the solver returns the four click coordinates.

Works either way: as a plugin of
[wulu-geetest-bypass](https://github.com/wulu007/geetest-bypass), which adds
click-track generation and submission, or standalone — the package exports
`solve_phrase()` and imports nothing from the main package.

## How it works

1. `detect.onnx` — a single-class YOLO model locates the four character boxes.
2. RapidOCR reads one CJK character from each box.
3. `order.onnx` scores every character at every one of the four positions; the
   24 permutations are ranked by total score and the best one wins.

The characters are read from the challenge image itself, so unlike `icon`/`word`
the solver needs no question thumbnails.

## Ordering

The click order is resolved in three tiers:

1. `dict.json` → `table` — answers verified online. Skipped when the four
   characters contain a duplicate, because a sorted key cannot say which box a
   repeated character sits in.
2. `dict.json` → `pending` — hand-curated hints, hoisted to the front of the
   model ranking.
3. `order.onnx` — the best-scoring permutation, with the `dict.json` → `tried`
   permutations (already known to be wrong) filtered out.

If locating or recognition does not yield exactly four characters, `solve_phrase`
returns an empty list rather than guessing.

## Accuracy

Measured 2026-10-15 on the public Geetest demo site
(`54088bb07d2df3c46b79f80300b0abbe`), one first guess each, no retries:

| Pipeline | Samples | First-guess pass rate |
| --- | --- | --- |
| Full — `table` dictionary, then `order.onnx` | 50 challenges | 49/50 = 98.0% |
| `order.onnx` alone — dictionary disabled | 151 character sets | 146/151 = 96.7% |

Reproduce the first row with `pytest tests/test_phrase.py -m accuracy`.

## Performance

Single process, CPU (`CPUExecutionProvider`), 40-image corpus. Locate and
recognize are timed per image, ordering per character set:

| Stage | Median | p95 |
| --- | --- | --- |
| locate | 9.3 ms | 11.6 ms |
| recognize | 36.6 ms | 42.1 ms |
| order (dictionary hit) | 0.0 ms | 0.0 ms |
| order (`order.onnx`) | 0.7 ms | 0.7 ms |
| **end to end** | **45.5 ms** | **53.8 ms** |

Recognition dominates. The tiered lookup is not a speed optimisation — both tiers
cost the same — it is there to raise accuracy.

## Model

| File | Size | Shape |
| --- | --- | --- |
| `detect.onnx` | 9.3 MiB | in `[1, 3, 320, 320]`, out `[1, 5, 2100]` |
| `order.onnx` | 12.4 MiB | in `input_ids` / `attention_mask`, out `[batch, seq, 4]` |
| `tokenizer.json` | 0.4 MiB | tokenizer for `order.onnx` |
| `dict.json` | 20 KiB | `table` / `tried` / `pending` |

`order.onnx` is a fine-tune of
[uer/chinese_roberta_L-2_H-128](https://huggingface.co/uer/chinese_roberta_L-2_H-128)
(Chinese RoBERTa Miniatures, pre-trained by
[UER-py](https://github.com/dbiir/UER-py)): a 4-way scoring head replaces the
masked-LM head, and `tokenizer.json` is built from the same 21128-token WordPiece
vocabulary. The upstream model card declares no license — see
[THIRD_PARTY_NOTICES.md](https://github.com/wulu007/geetest-bypass/blob/main/THIRD_PARTY_NOTICES.md).

## Download

Everything is fetched on first use into
`platformdirs.user_cache_dir('wulu-geetest-bypass', appauthor=False) / 'phrase'`
and SHA-256 verified against the registry in `hub.py`.

`hub.py` also runs as a script, which fetches all four files up front instead of
waiting for the first challenge:

```bash
python -m wulu_geetest_bypass_phrase.hub
```

If `huggingface.co` is unreachable, point `HF_ENDPOINT` at a mirror — the same
variable `huggingface_hub` reads, so anything already configured for it works
here too:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

`HF_ENDPOINT` is read when the package is first imported, so set it before the
solver runs.

## Usage

As a plugin of the main package:

```bash
uv add wulu-geetest-bypass[phrase]
```

The solver registers as an entry point of the `wulu_geetest_bypass.solvers`
group under the `phrase` captcha type, and is discovered automatically by
`wulu_geetest_bypass`.

```python
from wulu_geetest_bypass import Geetest

solver = Geetest(captcha_id='your_captcha_id', risk_type='phrase')
seccode = await solver.resolve()
```

Or standalone:

```bash
pip install wulu-geetest-bypass-phrase
```

```python
from wulu_geetest_bypass_phrase import solve_phrase

clicks = solve_phrase(image_bytes)  # [(x, y), ...] in 0~1, in click order
```
