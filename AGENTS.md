# wulu-geetest-bypass

Geetest CAPTCHA v4 bypass library. Pure Python, no Node.js.

## Commands

```bash
# install
uv sync --dev
uv sync --extra svg        # SVG solver (opencv, pillow, resvg-py)
uv sync --extra slide      # Slide solver (opencv)

# test
uv run pytest tests/ -k test_svg_seed  # single test
uv run pytest tests/                   # all tests

# lint
uv run ruff check src/
uv run ruff format --check src/
```

## Architecture

- **`Geetest`** (`geetest.py:44`): main class. Flow: `load()` → `verify()` → `generate_w()`
- **Solvers** in `solver/`: `match.py` (3×3), `slide.py` (opencv), `svg.py` (svg_seed + svg_icon), `winlinze.py` (goban), `voice.py` (KNN on MFCC)
- **Optional deps**: `[svg]` for SVG solvers, `[slide]` for slide, `[voice]` for voice (miniaudio + numpy)

## Key details

- Use `uv` not `pip`. Virtual env is `.venv`.
- All captcha types raise `VerifyError` after retries exhausted.
- Voice templates: `templates/voice_templates_*.npz` (~3KB each, KNN centroids).
- SVG solver (`svg.py`) handles both `svg_seed` and `svg_icon` with auto grid detection.
- Template matching: Canny edge + TM_CCORR_NORMED (background as 0 eliminates white-space bias).
- Never commit without explicit request. Use conventional commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`, `revert:`).
- Ruff config: single quotes, sort imports via `ruff check --fix`.
