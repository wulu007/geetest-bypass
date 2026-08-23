# wulu-geetest-bypass-nine

Nine-grid (3x3) solver for [wulu-geetest-bypass](https://github.com/wulu007/geetest-bypass).

> **Note**: This is an extension package for `wulu-geetest-bypass` and is not intended for standalone use. Install via the main package instead.

Uses `vit_small_patch16_dinov3` fused with the CLIP ViT-B/16 image tower
(via `timm`) to embed every cell of the 3x3 grid and the question icon(s),
then picks the cells whose object patches match the icon silhouette(s) best
with bidirectional patch matching.

## Installation

```bash
pip install wulu-geetest-bypass[nine]
```

## Plugin registration

This package registers its solver with the main package via the
`wulu_geetest_bypass.solvers` entry point group, so nine-grid captchas are
handled automatically once the package is installed.

## Usage

```python
from wulu_geetest_bypass import Geetest

g = Geetest(captcha_id='...', risk_type='nine')
seccode = await g.resolve()
```
