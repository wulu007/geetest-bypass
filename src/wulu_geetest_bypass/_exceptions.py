class GeetestError(Exception):
    pass


class RateLimitError(GeetestError):
    pass


class VerifyError(GeetestError):
    pass
