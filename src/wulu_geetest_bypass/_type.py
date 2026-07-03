from typing import Any, Literal, NotRequired, TypedDict

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
    proxy: NotRequired[str]
    lang: NotRequired[Lang]
    user_info: NotRequired[Any]
