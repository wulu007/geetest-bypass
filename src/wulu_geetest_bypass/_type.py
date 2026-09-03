from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NotRequired,
    Required,
    TypedDict,
)

Point = tuple[int, int]
ClickPos = Sequence[Point]
""" [[x, y], ...]   icon/word/phrase: 位置百分比"""
GridIndices = Sequence[Point]
""" [[row, col], ...]   nine: 网格索引 """
CoordPair = Sequence[Point]
""" [[row1, col1], [row2, col2]]   match/winlinze: 交换对 """
TracePoints = Sequence[tuple[float, float, int]]
""" [[x, y, t], ...]   pencil: 绘制轨迹 """
SvgGridPos = tuple[int, Point]
""" (frame, (row, col))   svg/space: 帧+网格 """

if TYPE_CHECKING:
    from wreq import Client
    from wreq.wreq import ClientConfig

RiskType = Literal[
    'ai',
    'slide',
    'match',
    'icon',
    'word',
    'nine',
    'phrase',
    'space',
    'pencil',
    'voice',
    'svg_icon',
    'svg_seed',
    'winlinze',
]
ClientType = Literal['web', 'web_mobile', 'android', 'ios']
Lang = Literal[
    'ara',
    'deu',
    'eng',
    'fra',
    'ind',
    'jpn',
    'kor',
    'por',
    'rus',
    'spa',
    'zh',
    'zho',
    'zho-hk',
]


# class WPayload(TypedDict):
#     captcha_id: str
#     captcha_type: RiskType
#     lot_number: str
#     pow_detail: dict[str, Any]
#     guard: bool
#     pt: str
#     bg: NotRequired[bytes]
#     slice: NotRequired[bytes]
#     ypos: NotRequired[int]
#     ques: NotRequired[list[list[int]]]
#     question_path: NotRequired[str]
#     answer_path: NotRequired[str]


class BasePayload(TypedDict):
    captcha_id: str
    lot_number: str
    pow_detail: dict[str, Any]
    guard: bool
    pt: int | str
    """
    Protocol type. Controls whether encryption is applied and which algorithm is used:
    - `0` → no encryption; the plaintext is directly returned via `urlsafe_encode`.
    - `1` → uses AES + RSA hybrid encryption.
    - `2` → uses SM4 + SM2 hybrid encryption.
    """
    language: NotRequired[str]


class AiPayload(BasePayload):
    captcha_type: Literal['ai']


class SlidePayload(BasePayload):
    captcha_type: Literal['slide']
    bg: bytes
    slice: bytes
    ypos: int


class SvgPayload(BasePayload):
    captcha_type: Literal['svg_seed', 'svg_icon']
    question_path: str
    answer_path: bytes


class MatchPayload(BasePayload):
    captcha_type: Literal['match', 'winlinze']
    ques: list[list[int]]


class ClickPayload(BasePayload):
    captcha_type: Literal['icon', 'word']
    imgs: bytes
    ques: list[bytes]


class NinePayload(BasePayload):
    captcha_type: Literal['nine']
    imgs: bytes
    ques: list[bytes]
    nine_nums: int


class ImagePayload(BasePayload):
    captcha_type: Literal['phrase', 'space', 'pencil']
    imgs: bytes


class VoicePayload(BasePayload):
    captcha_type: Literal['voice']
    voice_path: str
    voice_audio: bytes


WPayload = (
    AiPayload
    | SlidePayload
    | SvgPayload
    | MatchPayload
    | ClickPayload
    | NinePayload
    | ImagePayload
    | VoicePayload
)


class Seccode(TypedDict):
    captcha_id: str
    lot_number: str
    pass_token: str
    gen_time: str
    captcha_output: str


class VerifyData(TypedDict):
    lot_number: str
    result: str
    fail_count: int
    seccode: Seccode
    score: str
    payload: str
    process_token: str
    payload_protocol: int


class VerifyResponse(TypedDict):
    status: str
    data: VerifyData


class Encryption(Enum):
    NONE = 0
    AES_RSA = 1
    SM4_SM2 = 2


class GeetestOptions(TypedDict, total=False):
    captcha_id: Required[str]
    risk_type: RiskType
    client_type: ClientType
    challenge: str
    lang: Lang
    """ 语言, 默认zh """
    user_info: Any
    voice: bool
    """ 是否转为语音验证 """
    client: Client
    client_options: ClientConfig
    """ wreq.Client config dict """
    pt: Encryption | None
    """
    Encryption mode.

    - If `None` (default): the encryption mode is **automatically determined by the internal logic**
    - If set to a specific `Encryption` value (`NONE`, `AES_RSA`, or `SM4_SM2`): forces that mode,
    overriding the internal decision.

    Note:
    - `Encryption.NONE` means no encryption (direct `urlsafe_encode`).
    - `Encryption.AES_RSA` and `Encryption.SM4_SM2` enable hybrid encryption.
    """


AiSolver = Callable[[], None]
"""ai: no-op placeholder, never invoked."""
SlideSolver = Callable[[bytes, bytes, int], int]
"""slide: (bg, slice, ypos) -> setLeft px"""
SvgSolver = Callable[[str, str | bytes], SvgGridPos]
"""svg_seed/svg_icon: (question_path, answer_path) -> (frame, (row, col))"""
MatchSolver = Callable[[list[list[int]]], CoordPair | None]
"""match/winlinze: (ques) -> swap pairs"""
ClickSolver = Callable[[bytes, list[bytes]], ClickPos]
"""icon/word: (imgs, ques) -> click positions in percent"""
NineSolver = Callable[[bytes, list[bytes], int], GridIndices]
"""nine: (imgs, ques, nine_nums) -> grid indices"""
DrawSolver = Callable[[bytes], ClickPos | TracePoints]
"""phrase/space/pencil: (imgs) -> click positions or trace points"""
VoiceSolver = Callable[[bytes, str], str]
"""voice: (voice_audio, lang) -> digit sequence"""
