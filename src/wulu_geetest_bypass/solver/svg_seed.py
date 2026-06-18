import base64
import xml.etree.ElementTree as ET
from io import BytesIO

try:
    import cv2
    import numpy as np
    import resvg_py
    from PIL import Image
except ImportError as e:
    msg = f'missing optional dependency: {e.name}. Install with: pip install geetest-bypass[svg-seed]'
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
        g
        for g in root.iter(f'{{{_NS}}}g')
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

            g_attrib = dict(g_child.attrib)
            t = g_attrib.get('transform', '')
            if 'translate(' in t:
                idx = t.index('translate(')
                end = t.index(')', idx)
                g_attrib['transform'] = t[:idx] + 'translate(47.5,41.0' + t[end:]

            new_svg = ET.Element(
                f'{{{_NS}}}svg',
                {'width': '95', 'height': '82', 'viewBox': '0 0 95 82'},
            )
            new_g = ET.SubElement(new_svg, f'{{{_NS}}}g', g_attrib)
            for sub in g_child:
                new_g.append(sub)
            results.append(ET.tostring(new_svg, encoding='unicode'))

    if not results:
        raise ValueError('no valid grids extracted from SVG')
    return results


def match(svg: str, hint_b64: str) -> list[dict]:
    if not isinstance(svg, str) or not svg.strip():
        raise TypeError('svg must be a non-empty string')
    if not isinstance(hint_b64, str) or not hint_b64.strip():
        raise TypeError('hint_b64 must be a non-empty base64 string')

    try:
        hint_png = base64.b64decode(hint_b64)
    except Exception as e:
        raise ValueError(f'invalid hint base64: {e}') from e

    hint = _rgba_to_gray(hint_png)
    results = []

    for grid_svg in _grid_svgs(svg):
        try:
            png = resvg_py.svg_to_bytes(grid_svg)
        except Exception as e:
            raise RuntimeError(f'resvg render failed: {e}') from e

        gray = _rgba_to_gray(png)
        if gray.shape[0] < hint.shape[0] or gray.shape[1] < hint.shape[1]:
            raise RuntimeError(
                f'grid ({gray.shape[1]}x{gray.shape[0]}) smaller than hint ({hint.shape[1]}x{hint.shape[0]})'
            )

        _, score, _, _ = cv2.minMaxLoc(
            cv2.matchTemplate(gray, hint, cv2.TM_CCOEFF_NORMED)
        )
        results.append({'grid': len(results) + 1, 'score': round(float(score), 6)})

    results.sort(key=lambda r: r['score'], reverse=True)
    return results


def solve_svg(svg: str, hint_b64: str):
    results = match(svg, hint_b64)
    best = results[0]['grid']
    layer = (best - 1) // 9
    inner = (best - 1) % 9 + 1
    row = (inner - 1) // 3
    col = (inner - 1) % 3
    return layer, (row + 1, col + 1)
