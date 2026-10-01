from enum import StrEnum


class GeetestError(Exception):
    pass


class ConfigError(GeetestError):
    pass


class RateLimitError(GeetestError):
    pass


class VerifyError(GeetestError):
    pass


class ErrorCode(StrEnum):
    """``code`` values the server puts in a ``status: "error"`` body."""

    RISK_TYPE = '-50001'
    """``risk_type`` is malformed, badly signed, expired or already used."""
    PARAM_DECRYPT = '-50002'
    """``w`` could not be decrypted."""
    JSONP_XSS = '-50004'
    """``callback`` is not ``geetest_<digits>``."""
    LOT_NUMBER_MISSING = '-50302'
    LOT_NUMBER_INVALID = '-50303'


class ApiError(GeetestError):
    """The server answered ``status: "error"`` — the HTTP status is still 200."""

    def __init__(self, what: str, data: dict) -> None:
        self.what = what
        self.code = data.get('code')
        self.msg = data.get('msg')
        self.desc = data.get('desc')
        super().__init__(f'{what} rejected: {self.code} {self.msg} / {self.desc}')
