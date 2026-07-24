# wulu-geetest-bypass

Geetest CAPTCHA v4 bypass library. Pure Python 3.11+, no Node.js.

## Commands

```bash
# install
uv sync --dev
uv sync --extra svg        # svg solver (pillow, resvg-py, opencv)
uv sync --extra slide      # slide solver (opencv)

# run all tests
uv run pytest tests/

# focused test
uv run pytest tests/ -k test_svg_seed  -v

# lint (ruff — only import sorting)
uv run ruff check --fix src/
uv run ruff format src/

# build
uv build

# publish (requires PyPI token)
uv publish
```

- Ruff config: single quotes, `I` rule only (import sorting).
- `ruff check` → `ruff format` — order matters when `--fix` rewrites imports.
- pytest has `addopts = "-s"` (stdout not captured).
- CI lint runs `uvx ruff check` (no install needed), publish on tag push only.

## Architecture

- **`Geetest`** (`geetest.py:34`): main class. Flow: `load()` → `verify()` (calls `generate_w()` internally) → returns `Seccode`. User-facing: `resolve(retry=3)` wraps both.
- **Solvers** in `solver/`: lazy-loaded via `__getattr__` — missing optional deps return a stub raising `ImportError`. Solvers: `match.py` (3×3), `slide.py` (opencv gradient morphology + TM_CCOEFF_NORMED), `svg.py` (svg_seed + svg_icon, auto grid detection), `winlinze.py` (goban).
- **`crypto.py`**: `build_w()` encrypts payload. `pt=0` → base64, `pt=1` → AES-128-CBC + RSA-1024, `pt=2` → SM4-CBC + SM2.
- **`config.py`**: auto-updated daily by cron CI (`scripts/update_config.py` runs `scripts/extract-config.mjs` with Node.js). Patrol config values change; `em`, `gee_guard`, and constants do not.
- **Voice templates** (`.npz`): not bundled in the main wheel. Stored in `extensions/wulu-geetest-bypass-voice/src/wulu_geetest_bypass_voice/` as a separate installable package (files named `{lang}.npz`). The `voice` extra pulls in `wulu-geetest-bypass-voice`. Run `scripts/build_voice_templates.py` to regenerate. Package metadata and README in `extensions/wulu-geetest-bypass-voice/pyproject.toml`.

## Key gotchas

- Use `uv` not `pip`. Virtual env is `.venv`.
- Optional dep chain: `image` (opencv) is intermediate → `slide` depends on `image`, `svg` depends on `image` + pillow + resvg-py.
- Solver lazy loading: `from wulu_geetest_bypass.solver import solve_slide` raises `ImportError` if opencv missing, with install hint.
- SVG solver (`svg.py`): `_grid_svgs()` extracts grid SVGs by `geetest_frame_hash` / `geetest_grid_hash`. Auto-detects 4-grid (2 cols) vs 9-grid (3 cols). Uses `resvg_py` for SVG→PNG rasterization.
- Slide solver (`slide.py`): morphology gradient (3×3 rect) + `TM_CCOEFF_NORMED`. Alpha channel → background forced to 0 (eliminates white-space bias).
- Custom solver registration: `Geetest.register_solver('icon', my_func)`.
- Never commit without explicit request. Conventional commits: `feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`, `revert:`.
- Daily config-update CI (`update-config.yml`) commits to `main` directly and bumps patch version + tags.
