import base64
import re
import xml.etree.ElementTree as ET
from io import BytesIO

try:
    import cv2
    import numpy as np
    import resvg_py
    from PIL import Image
except ImportError as e:
    msg = f'missing optional dependency: {e.name}. Install with: pip install geetest-bypass[svg]'
    raise ImportError(msg) from e

_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', _NS)


def _rgba_to_gray(png: bytes) -> np.ndarray:
    img = Image.open(BytesIO(png))
    if img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2GRAY)
    return cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2GRAY)


def _grid_svgs(svg: str) -> list[str]:
    root = ET.fromstring(svg)
    frames = [
        g for g in root.iter(f'{{{_NS}}}g')
        if 'geetest_frame_hash' in (g.get('class') or '')
    ]
    if not frames:
        raise ValueError('no geetest_frame_hash found in SVG')

    results = []
    for frame in frames:
        children = list(frame)
        for i, child in enumerate(children):
            if not child.tag.endswith('rect'):
                continue
            if 'geetest_grid_hash' not in (child.get('class') or ''):
                continue
            if i + 1 >= len(children):
                continue
            g_child = children[i + 1]
            if not g_child.tag.endswith('g'):
                continue

            w = float(child.get('width', 0))
            h = float(child.get('height', 0))
            if w == 0 or h == 0:
                continue
            cx, cy = w / 2, h / 2

            g_attrib = dict(g_child.attrib)
            t = g_attrib.get('transform', '')
            if 'translate(' in t:
                idx = t.index('translate(')
                end = t.index(')', idx)
                after = t[end:]
                after = re.sub(r'scale\([\d.]+\)', 'scale(1)', after)
                g_attrib['transform'] = t[:idx] + f'translate({cx},{cy}' + after

            new_svg = ET.Element(
                f'{{{_NS}}}svg',
                {'width': str(w), 'height': str(h), 'viewBox': f'0 0 {w} {h}'},
            )
            new_g = ET.SubElement(new_svg, f'{{{_NS}}}g', g_attrib)
            for sub in g_child:
                new_g.append(sub)
            results.append(ET.tostring(new_svg, encoding='unicode'))

    if not results:
        raise ValueError('no valid grids extracted from SVG')
    return results


def _decode_hint(hint: str | bytes) -> bytes:
    if isinstance(hint, bytes):
        return hint
    if isinstance(hint, str):
        try:
            return base64.b64decode(hint)
        except Exception as e:
            raise ValueError(f'invalid hint base64: {e}') from e
    raise TypeError('hint must be str or bytes')


def match(svg: str, hint: str | bytes) -> list[dict]:
    if not isinstance(svg, str) or not svg.strip():
        raise TypeError('svg must be a non-empty string')

    hint_png = _decode_hint(hint)
    hint_edge = cv2.Canny(_rgba_to_gray(hint_png), 50, 150)
    results = []

    for grid_svg in _grid_svgs(svg):
        png = resvg_py.svg_to_bytes(grid_svg)
        grid_edge = cv2.Canny(_rgba_to_gray(png), 50, 150)

        _, score, _, _ = cv2.minMaxLoc(
            cv2.matchTemplate(grid_edge, hint_edge, cv2.TM_CCORR_NORMED)
        )
        results.append({'grid': len(results) + 1, 'score': round(float(score), 6)})

    results.sort(key=lambda r: r['score'], reverse=True)
    return results


def solve_svg(svg: str, hint: str | bytes):
    results = match(svg, hint)
    grids = _grid_svgs(svg)
    cells_per_frame = len(grids) // 3
    cols = 2 if cells_per_frame == 4 else 3

    best = results[0]['grid']
    layer = (best - 1) // cells_per_frame
    inner = (best - 1) % cells_per_frame + 1
    row = (inner - 1) // cols
    col = (inner - 1) % cols
    return layer, (row + 1, col + 1)
