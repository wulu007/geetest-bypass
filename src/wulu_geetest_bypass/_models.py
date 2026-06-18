from typing import Any, Literal, NotRequired, TypedDict

from wreq import Client

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


class WPayload(TypedDict):
    captcha_id: str
    captcha_type: RiskType
    lot_number: str
    pow_detail: dict[str, Any]
    guard: bool
    pt: str
    bg: NotRequired[bytes]
    slice: NotRequired[bytes]
    ypos: NotRequired[int]
    ques: NotRequired[list[list[int]]]
    question_path: NotRequired[str]
    answer_path: NotRequired[str]


class GeetestOptions(TypedDict):
    captcha_id: str
    risk_type: NotRequired[RiskType]
    client_type: NotRequired[ClientType]
    challenge: NotRequired[str]
    proxy: NotRequired[str]
    client: NotRequired[Client]
    lang: NotRequired[Lang]
    user_info: NotRequired[Any]
