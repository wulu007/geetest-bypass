class GeetestError(Exception):
    pass


class ConfigError(GeetestError):
    pass


class RateLimitError(GeetestError):
    pass


class VerifyError(GeetestError):
    pass
