import base64
import re
import xml.etree.ElementTree as ET
from io import BytesIO

import cv2
import numpy as np
import resvg_py
from PIL import Image

_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', _NS)
_SHAPES = {'path', 'circle', 'ellipse', 'rect', 'polygon', 'polyline', 'line'}

_LAYOUT_PARAMS = {
    'seed': ((12.0, 14.0, 16.0), (1.3, 1.4, 1.5)),
    'icon_2x2': ((0.0,), (0.5,)),
    'icon_3x3': ((0.0,), (1.0,)),
}

# 第一组参数就够有把握时不再搜其余组合：分数够高且领先第 2 名够多
_CONFIDENT_SCORE = 0.35
_CONFIDENT_MARGIN = 0.06


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

            w = float(child.get('width', 0))
            h = float(child.get('height', 0))
            if w == 0 or h == 0:
                continue
            cx, cy = w / 2, h / 2

            g_attrib = dict(g_child.attrib)
            # 有的 build 用 style="fill:…"，有的用 fill="…"/stroke="…" 属性，两种都算自带样式
            styled = any(
                sub.get('style') or sub.get('fill') or sub.get('stroke')
                for sub in g_child.iter()
            )
            scale = 1
            t = g_attrib.get('transform', '')
            if 'translate(' in t:
                idx = t.index('translate(')
                end = t.index(')', idx)
                after = t[end:]
                after = re.sub(r'scale\(-?[\d.]+\)', f'scale({scale})', after)
                after = re.sub(r'rotate\(-?[\d.]+\)', 'rotate(0)', after)
                g_attrib['transform'] = t[:idx] + f'translate({cx},{cy}' + after

            if not styled:
                g_attrib['fill'] = 'none'
                g_attrib['stroke'] = '#000'
                g_attrib['stroke-width'] = '2'
                g_attrib['stroke-linecap'] = 'round'
                g_attrib['stroke-linejoin'] = 'round'

            bg_attrib = dict(child.attrib)
            bg_attrib.pop('x', None)
            bg_attrib.pop('y', None)

            new_svg = ET.Element(
                f'{{{_NS}}}svg',
                {'width': str(w), 'height': str(h), 'viewBox': f'0 0 {w} {h}'},
            )
            new_g = ET.SubElement(new_svg, f'{{{_NS}}}g', g_attrib)
            for sub in g_child:
                new_g.append(sub)
            # 没写 fill 的形状按 SVG 默认会填成黑色，hint 是描边版，统一改成不填充
            for el in new_g.iter():
                if el.tag.rsplit('}', 1)[-1] not in _SHAPES:
                    continue
                if el.get('fill') is None and 'fill' not in (el.get('style') or ''):
                    el.set('fill', 'none')
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


def _hint_to_edge(hint: str | bytes) -> np.ndarray:
    hint_png = _decode_hint(hint)
    # Geetest has enhanced the interference of Hint
    # Apply denoising and smoothing to the hint
    denoised = cv2.medianBlur(_rgba_to_gray(hint_png), 3)
    smooth = cv2.bilateralFilter(denoised, d=5, sigmaColor=50, sigmaSpace=50)
    return cv2.Canny(smooth, 50, 150)


def _layout_params(
    svg: str, cells_per_frame: int
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """按 SVG 结构选参数：svg_seed 带 data-captcha-type，svg_icon 靠每帧格数区分布局。"""
    if re.search(r'data-captcha-type\s*=\s*["\']geetest-svg["\']', svg):
        return _LAYOUT_PARAMS['seed']
    return _LAYOUT_PARAMS['icon_2x2' if cells_per_frame == 4 else 'icon_3x3']


def grid_cols(svg: str) -> int:
    """按格子 rect 的 x 坐标去重算列数，不依赖题型或版本号。"""
    root = ET.fromstring(svg)
    for frame in root.iter(f'{{{_NS}}}g'):
        if 'geetest_frame_hash' not in (frame.get('class') or ''):
            continue
        xs = {
            round(float(rect.get('x', 0)), 1)
            for rect in list(frame)
            if rect.tag.endswith('rect')
            and 'geetest_grid_hash' in (rect.get('class') or '')
        }
        if xs:
            return len(xs)
    raise ValueError('no geetest_grid_hash found in SVG')


def _transform_edge(edge: np.ndarray, angle: float, scale: float) -> np.ndarray:
    if angle:
        h, w = edge.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        edge = cv2.warpAffine(edge, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    if scale != 1.0:
        edge = cv2.resize(edge, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return edge


def match(svg: str, hint: str | bytes) -> list[dict]:
    if not isinstance(svg, str) or not svg.strip():
        raise TypeError('svg must be a non-empty string')

    grids = _grid_svgs(svg)
    angles, scales = _layout_params(svg, len(grids) // 3)
    edges = [cv2.Canny(_rgba_to_gray(resvg_py.svg_to_bytes(g)), 50, 150) for g in grids]
    base = _hint_to_edge(hint)
    best = np.full(len(edges), -1.0)

    combos = [(angle, scale) for angle in angles for scale in scales]
    for index, (angle, scale) in enumerate(combos):
        tpl = _transform_edge(base, angle, scale)
        for i, grid_edge in enumerate(edges):
            if tpl.shape[0] > grid_edge.shape[0] or tpl.shape[1] > grid_edge.shape[1]:
                continue
            score = cv2.minMaxLoc(
                cv2.matchTemplate(grid_edge, tpl, cv2.TM_CCOEFF_NORMED)
            )[1]
            if score > best[i]:
                best[i] = score
        if index == 0 and len(combos) > 1 and len(best) > 1:
            order = np.sort(best)[::-1]
            if (
                order[0] >= _CONFIDENT_SCORE
                and order[0] - order[1] >= _CONFIDENT_MARGIN
            ):
                break

    if (best < 0).all():
        raise RuntimeError(
            f'hint ({base.shape[1]}x{base.shape[0]}) larger than every grid at all scales'
        )

    results = [{'grid': i + 1, 'score': round(float(s), 4)} for i, s in enumerate(best)]
    results.sort(key=lambda r: r['score'], reverse=True)
    return results


def _keyframe_block(svg: str, n: int) -> str:
    m = re.search(rf'@keyframes geetest_frame{n}_animation_hash\s*\{{', svg)
    if m is None:
        raise ValueError(f'no @keyframes for frame {n} in SVG')
    start = m.end() - 1
    depth = 0
    for i in range(start, len(svg)):
        if svg[i] == '{':
            depth += 1
        elif svg[i] == '}':
            depth -= 1
            if depth == 0:
                return svg[start : i + 1]
    raise ValueError(f'unbalanced @keyframes for frame {n} in SVG')


def frame_times(svg: str) -> list[tuple[int, int]]:
    """Parse each frame's visible time window (ms) from the SVG animation.

    Returns [(s1,e1), (s2,e2), (s3,e3)] — for each frame, the time span during
    which its opacity is > 0 (visible), derived from the @keyframes steps and
    the animation duration.
    """
    duration = None
    for m in re.finditer(r'geetest_frame\d_animation_hash\s+([\d.]+)s', svg):
        duration = float(m.group(1))
        break
    if duration is None:
        raise ValueError('no frame animation duration found in SVG')

    total = round(duration * 1000)
    frames = []
    for n in range(1, 4):
        block = _keyframe_block(svg, n)
        steps = [
            (float(p), float(o))
            for p, o in re.findall(r'([\d.]+)%\s*\{\s*opacity:\s*([\d.]+)', block)
        ]
        visible = [p for p, o in steps if o > 0]
        start = round(min(visible) / 100 * total)
        end = round(max(visible) / 100 * total)
        frames.append((start, end))

    return frames


def solve_svg(svg: str, hint: str | bytes) -> tuple[int, tuple[int, int], int]:
    results = match(svg, hint)
    grid_count = svg.count('geetest_grid_hash')
    cells_per_frame = grid_count // 3
    cols = grid_cols(svg)

    best = results[0]['grid']
    layer = (best - 1) // cells_per_frame
    inner = (best - 1) % cells_per_frame + 1
    row = (inner - 1) // cols
    col = (inner - 1) % cols
    return layer, (row + 1, col + 1), cols
