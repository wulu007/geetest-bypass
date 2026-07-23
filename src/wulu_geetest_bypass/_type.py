from typing import TYPE_CHECKING, Any, Literal, NotRequired, Sequence, TypedDict

Point = tuple[int, int]
ClickPos = Sequence[Point]
""" [[x, y], ...]   icon/word/phrase: 位置百分比×100 """
GridIndices = Sequence[Point]
""" [[row, col], ...]   nine: 网格索引 """
CoordPair = Sequence[Point]
""" [[row1, col1], [row2, col2]]   match/winlinze: 交换对 """
TracePoints = Sequence[tuple[float, float, int]]
""" [[x, y, t], ...]   pencil: 绘制轨迹 """
SvgGridPos = tuple[int, Point]
""" (frame, (row, col))   svg/space: 帧+网格 """

if TYPE_CHECKING:
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
Lang = Literal['zh', 'en', 'zho', 'eng']


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
    pt: str


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


class GeetestOptions(TypedDict):
    captcha_id: str
    risk_type: NotRequired[RiskType]
    client_type: NotRequired[ClientType]
    challenge: NotRequired[str]
    lang: NotRequired[Lang]
    user_info: NotRequired[Any]
    client_options: NotRequired['ClientConfig']
