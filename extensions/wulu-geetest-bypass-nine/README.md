# wulu-geetest-bypass-nine

Offline **nine-grid** solver for Geetest v4 CAPTCHAs. The challenge is a 3×3 grid
plus a prompt icon; the solver picks the cells that show the same object and
returns their grid positions.

Works either way: as a plugin of
[wulu-geetest-bypass](https://github.com/wulu007/geetest-bypass), which adds
click-track generation and submission, or standalone — the package exports
`solve_nine()` and imports nothing from the main package.

## How it works

A single end-to-end ONNX neural classifier:

1. **Prompt class lookup**: The prompt icon's MD5 hash is matched against the
   class registry (from ONNX custom metadata `classes` or environment variables),
   resolving the target category index.
2. **Grid preprocessing**:
   - The grid image carries a **2px black bar at the bottom** (all collected
     samples do), so `bar_rows()` trims it before cutting.
   - The three-way boundaries start at `ceil(i * h / 3)` — the real seams sit at
     rows 87 and 173 of the 259-tall content (i.e. `ceil(86.33)` and
     `ceil(172.67)`), while every cell is `h // 3 = 86` tall, cleanly dropping
     the seam row:

```
0..85   87..172   173..258      86 rows each, seams exactly between cells
```

3. **Batch inference**:
   - All 9 cells are cropped, resized to the model's expected resolution (auto-detected
     from the ONNX graph, default 128×128), and normalized with ImageNet mean and std.
   - The resulting tensor of shape `(9, 3, H, W)` is fed into `nine.onnx` in
     a single forward pass.
   - The logits corresponding to the target prompt class index `logits[:, target_idx]`
     rank the cells by matching confidence.
   - The top `nine_nums` cells are returned in click order.

## Model

| File | Size | Type | Input Shape | Output Shape |
| --- | --- | --- | --- | --- |
| `nine.onnx` | ~14 MiB | CNN Classifier | `image [batch, 3, 128, 128]` | `logits [batch, num_classes]` |

Category metadata (`classes`) is embedded directly in the ONNX file's custom
metadata map as a comma-separated list of prompt icon hashes.

## Custom Model Integration

You can provide your own trained ONNX model weights without modifying any code. Point the environment variable `NINE_MODEL_PATH` to your model file:

```bash
export NINE_MODEL_PATH=/path/to/your_custom_model.onnx
```

### Model Requirements

1. **Input Tensor**:
   - **Shape**: `[batch, 3, H, W]` (e.g. `[batch, 3, 128, 128]`, `[batch, 3, 224, 224]`, or arbitrary `H×W`). The solver automatically inspects the ONNX graph's input shape to resize candidate cells. If dimensions are dynamic or unspecified, it defaults to `128×128`.
   - **Node name**: Arbitrary (auto-detected via `session.get_inputs()[0].name`).
   - **Normalization**: RGB format normalized with ImageNet statistics:
     `mean = [0.485, 0.456, 0.406]`, `std = [0.229, 0.224, 0.225]`.

2. **Output Tensor**:
   - **Shape**: `[batch, num_classes]` returning raw classification logits for each grid cell.
   - **Node name**: Arbitrary (auto-detected via `session.get_outputs()[0].name`).

3. **Class Mapping (`classes`)**:
   The solver matches each prompt icon by its MD5 hex digest against the target output column index. You can provide this mapping via either of two methods:
   - **Method A (Recommended — Embed into ONNX metadata)**:
     ```python
     import onnx

     model = onnx.load('your_model.onnx')
     meta = model.metadata_props.add()
     meta.key = 'classes'
     meta.value = ','.join(class_md5_hashes)  # e.g. "0259c3ab...,16a04e9c..."
     onnx.save(model, 'your_model.onnx')
     ```
   - **Method B (Environment Variables)**:
     - Set `NINE_CLASSES_PATH=/path/to/classes.txt` (newline-separated or comma-separated list of hashes, or a JSON array), or
     - Set `NINE_CLASSES=hash1,hash2,hash3,...`.

## Performance

Single process, CPU (`CPUExecutionProvider`), batched 9-cell inference:

| Function | Latency (CPU) |
| --- | --- |
| `solve_nine` | ~15–25 ms |

## Download

The model file is fetched on first use into
`platformdirs.user_cache_dir('wulu-geetest-bypass', appauthor=False) / 'nine'`
and SHA-256 verified against the registry in `hub.py`.

`hub.py` also runs as a script, which fetches the file up front instead of
waiting for the first challenge:

```bash
python -m wulu_geetest_bypass_nine.hub
```

If `huggingface.co` is unreachable, point `HF_ENDPOINT` at a mirror — the same
variable `huggingface_hub` reads:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

`HF_ENDPOINT` is read when the package is first imported, so set it before the
solver runs.

## Usage

As a plugin of the main package:

```bash
uv add wulu-geetest-bypass[nine]
```

The solver registers as an entry point of the `wulu_geetest_bypass.solvers`
group under the `nine` captcha type, and is discovered automatically by
`wulu_geetest_bypass`.

```python
from wulu_geetest_bypass import Geetest

solver = Geetest(captcha_id='your_captcha_id', risk_type='nine')
seccode = await solver.resolve()
```

Or standalone:

```bash
pip install wulu-geetest-bypass-nine
```

```python
from wulu_geetest_bypass_nine import solve_nine

cells = solve_nine(grid_bytes, [prompt_bytes], 3)
# [[row, col], ...] 1-based, in click order — e.g. [[1, 1], [3, 3], [1, 3]]
```

Grid positions are 1-based on both axes, matching the SDK's `userresponse`
(`dataId` is `1..3`); `score_nine()` returns the same ranking as raw logits if
you need the scores.
