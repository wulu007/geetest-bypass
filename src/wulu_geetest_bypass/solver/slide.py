try:
    import cv2
    import numpy as np
except ImportError as e:
    msg = f'missing optional dependency: {e.name}. Install with: pip install geetest-bypass[slide]'
    raise ImportError(msg) from e


def solve_slide(bg_bytes: bytes, slice_bytes: bytes, ypos: int = 0) -> int:
    bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
    sl = cv2.imdecode(np.frombuffer(slice_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)

    if sl.shape[2] == 4:
        alpha_channel = sl[:, :, 3]
        sl_gray = cv2.cvtColor(sl, cv2.COLOR_BGR2GRAY)
        sl_gray[alpha_channel == 0] = 0  # 将透明部分强制置黑
    else:
        sl_gray = cv2.cvtColor(sl, cv2.COLOR_BGR2GRAY)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mg_bg = cv2.morphologyEx(bg_gray, cv2.MORPH_GRADIENT, kernel)
    mg_sl = cv2.morphologyEx(sl_gray, cv2.MORPH_GRADIENT, kernel)

    if ypos > 0 and ypos + mg_sl.shape[0] <= mg_bg.shape[0]:
        search_bg = mg_bg[ypos : ypos + mg_sl.shape[0], :]
    else:
        search_bg = mg_bg

    # 5. 模板匹配
    res = cv2.matchTemplate(search_bg, mg_sl, cv2.TM_CCOEFF_NORMED)
    max_loc = cv2.minMaxLoc(res)[-1]
    return max_loc[0]


# def solve_slide_v2(bg_bytes: bytes, slice_bytes: bytes, ypos: int = 0) -> int:
#     bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
#     sl = cv2.imdecode(np.frombuffer(slice_bytes, np.uint8), cv2.IMREAD_UNCHANGED)

#     bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)

#     if sl.shape[2] == 4:
#         alpha = sl[:, :, 3]
#         sl_gray = cv2.cvtColor(sl, cv2.COLOR_BGR2GRAY)
#         sl_gray[alpha == 0] = 0
#     else:
#         sl_gray = cv2.cvtColor(sl, cv2.COLOR_BGR2GRAY)

#     # 按 ypos 裁剪背景搜索区域（覆盖滑块高度 + 少量余量）
#     h_sl = sl_gray.shape[0]
#     margin = 10
#     ys = max(0, ypos - margin)
#     ye = min(bg.shape[0], ypos + h_sl + margin)

#     edge_bg = cv2.Canny(bg_gray[ys:ye], 150, 200)
#     edge_sl = cv2.Canny(sl_gray, 150, 200)

#     edge_bg = cv2.cvtColor(edge_bg, cv2.COLOR_GRAY2RGB)
#     edge_sl = cv2.cvtColor(edge_sl, cv2.COLOR_GRAY2RGB)

#     res = cv2.matchTemplate(edge_bg, edge_sl, cv2.TM_CCOEFF_NORMED)
#     _, _, _, max_loc = cv2.minMaxLoc(res)
#     return max_loc[0]
