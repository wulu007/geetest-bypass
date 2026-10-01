from enum import StrEnum


class GeetestError(Exception):
    pass


class ConfigError(GeetestError):
    pass


class RateLimitError(GeetestError):
    pass


class VerifyError(GeetestError):
    """``/verify`` answered with a ``result`` other than ``success``.

    ``result`` is the raw server value:

    - ``fail`` — scored and rejected (wrong answer, bad headers, low risk score).
      Retryable.
    - ``forbidden`` — rejected before scoring: an IP-level rate limit, not an
      answer problem. The same code and headers pass again once the window clears,
      so back off or change the exit IP instead of retrying in a tight loop.
    - ``continue`` — the server wants another round of the same challenge (``match``).
    """

    def __init__(self, data: dict, attempts: int = 1) -> None:
        self.result = data['result']
        self.fail_count = data.get('fail_count', 0)
        self.attempts = attempts
        super().__init__(
            f'verify {self.result} (fail_count={self.fail_count}) after {attempts} attempt(s)'
        )

    @property
    def is_fail(self) -> bool:
        """Scored and rejected — worth retrying."""
        return self.result == 'fail'

    @property
    def is_forbidden(self) -> bool:
        """Rejected before scoring (IP rate limit) — retrying only makes it worse."""
        return self.result == 'forbidden'


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
