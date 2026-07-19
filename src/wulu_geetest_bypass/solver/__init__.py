import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .match import solve_match
    from .slide import solve_slide
    from .svg import solve_svg
    from .voice import solve_voice
    from .winlinze import solve_winlinze


__all__ = [
    'solve_match',
    'solve_slide',
    'solve_svg',
    'solve_voice',
    'solve_winlinze',
]


def __getattr__(name):
    if name in __all__:
        module_name = name.replace('solve_', '', 1)
        try:
            module = importlib.import_module(f'.{module_name}', package=__name__)
            return getattr(module, name)
        except ImportError as e:
            err = e

            def _missing_dependency_stub(*args, **kwargs):
                raise ImportError(
                    f"'{name}' requires optional dependencies. "
                    f'Install the corresponding extra (e.g. uv add wulu-geetest-bypass[{module_name}]). '
                    f'Underlying error: {err}'
                ) from err

            return _missing_dependency_stub

    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return __all__
