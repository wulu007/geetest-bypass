from functools import lru_cache
from io import BytesIO

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

# (model_name, patch_grid, weight) — vit_small_patch16_dinov3 and CLIP's
# image tower give complementary signals; fusing them beats either alone.
_MODELS = [
    ('vit_small_patch16_dinov3', 0.30),
    ('vit_base_patch16_clip_224.openai', 0.70),
]
_TOP_K = 8


def solve_nine(imgs: bytes, ques: list[bytes], nine_nums: int) -> list[list[int]]:
    """Solve a Geetest v4 'nine' (3x3 grid) captcha.

    Splits the grid image into a 3x3 grid, embeds every cell and every
    question icon with ``vit_small_patch16_dinov3`` + the CLIP ViT-B/16
    image tower, then returns the ``nine_nums`` cells whose object patches
    match the question icon silhouette(s) best.

    The question icons are RGBA black silhouettes; they are cropped to the
    non-transparent bounding box, composited on white, and only patches
    overlapping the silhouette ink are kept as the query. Each cell is scored
    by bidirectional patch matching (every query patch -> its best cell patch,
    plus every cell patch -> its best query patch), averaged over the two
    models with fixed weights.

    Args:
        imgs: bytes of the 3x3 grid sprite (PNG/JPG).
        ques: bytes of each question icon.
        nine_nums: number of cells to click.

    Returns:
        [[row, col], ...] 0-based grid indices, sorted by similarity desc.
    """
    order, _ = score_nine(imgs, ques)
    return [[i // 3, i % 3] for i in order[:nine_nums]]


def score_nine(imgs: bytes, ques: list[bytes]) -> tuple[list[int], list[float]]:
    """Score every grid cell against the question icon(s).

    Returns ``(order, scores)`` where ``order`` lists the 9 cell indices sorted
    by descending score and ``scores`` holds the fused similarity per cell
    (0..8, cell index = row * 3 + col).
    """
    grid = Image.open(BytesIO(imgs)).convert('RGB')
    cells = _split_grid(grid)

    question_cells = [_icon_rgb(BytesIO(q)) for q in ques]

    scores = {}
    for model_name, weight in _MODELS:
        extract, patch_grid = _get_model(model_name)
        q_patches = _question_patches(question_cells, extract, patch_grid)
        for i, cell in enumerate(cells):
            cell_patches = extract(cell)
            fwd = (q_patches @ cell_patches.T).max(dim=1).values
            bwd = (cell_patches @ q_patches.T).max(dim=1).values
            score = (
                0.5 * fwd.mean() + 0.5 * bwd.topk(min(_TOP_K, len(bwd))).values.mean()
            )
            scores[i] = scores.get(i, 0.0) + weight * score.item()

    order = sorted(range(9), key=lambda i: scores[i], reverse=True)
    return order, [scores[i] for i in range(9)]


def _split_grid(img: Image.Image) -> list[Image.Image]:
    w, h = img.size
    cw, ch = w // 3, h // 3
    return [
        img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
        for r in range(3)
        for c in range(3)
    ]


def _icon_rgb(q: BytesIO) -> Image.Image:
    """Crop an RGBA silhouette to its opaque bbox and composite on white."""
    icon = Image.open(q).convert('RGBA')
    alpha = np.asarray(icon)[:, :, 3] > 100
    ys, xs = np.where(alpha)
    if len(ys):
        icon = icon.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    bg = Image.new('RGBA', icon.size, (255, 255, 255, 255))
    bg.alpha_composite(icon)
    return bg.convert('RGB')


def _question_patches(
    icons: list[Image.Image], extract, patch_grid: int
) -> torch.Tensor:
    """Patch features of the silhouette ink only (one set per icon, concat)."""
    patches = []
    for icon in icons:
        feats = extract(icon)  # (N, C)
        gray = np.asarray(icon.resize((patch_grid * 16, patch_grid * 16)).convert('L'))
        mask = np.zeros((patch_grid * patch_grid,), dtype=bool)
        for p in range(patch_grid * patch_grid):
            r, c = divmod(p, patch_grid)
            mask[p] = gray[r * 16 : (r + 1) * 16, c * 16 : (c + 1) * 16].mean() < 200
        patches.append(feats[mask])
    return torch.cat(patches)  # (total_nq, C)


@lru_cache(maxsize=2)
def _get_model(model_name: str):
    import timm
    from timm.data.config import resolve_data_config
    from timm.data.transforms_factory import create_transform

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = timm.create_model(model_name, pretrained=True).to(device)
    model.eval()
    config = resolve_data_config({}, model=model)
    transform = create_transform(**config)
    patch_grid = config['input_size'][1] // 16
    has_register = 'dinov3' in model_name

    @torch.no_grad()
    def extract(img: Image.Image) -> torch.Tensor:
        batch = transform(img).unsqueeze(0).to(device)
        feats = model.forward_features(batch)
        feats = feats[0]
        if has_register:
            feats = feats[1 : 1 + patch_grid * patch_grid]  # drop cls + reg tokens
        else:
            feats = feats[1:]
        return F.normalize(feats, dim=1)

    return extract, patch_grid
