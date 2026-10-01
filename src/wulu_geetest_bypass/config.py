import json
import re
from importlib.resources import files
from typing import ClassVar, NamedTuple

from ._exceptions import ConfigError


class Patrol(NamedTuple):
    biht: str
    lib_key: str
    lib_val: str
    abo_key: str
    abo_val: str
    track_enable: bool


class Config:
    gee_guard: ClassVar = {
        'roe': {
            'aup': '3',
            'sep': '3',
            'egp': '3',
            'auh': '3',
            'rew': '3',
            'snh': '3',
            'res': '3',
            'cdc': '3',
        }
    }

    em: ClassVar = {
        'cp': 0,
        'ek': '11',
        'nt': 0,
        'ph': 0,
        'sc': 0,
        'si': 0,
        'wd': 1,
    }

    _patrols: ClassVar[dict[str, Patrol]] = {}

    @staticmethod
    def _ver(static_path: str | None) -> str:
        return (static_path or '').removeprefix('/v4/static/')

    @classmethod
    def register_patrol(cls, static_path: str, patrol: Patrol) -> None:
        """Register patrol values for a build, taking priority over ``data/*.json``.

        Also the escape hatch for a build the daily job has not recorded yet::

            Config.register_patrol('/v4/static/v1.9.7-fc2ddc', Patrol(...))

        To change a single field of a known build, start from its resolved values::

            cfg = Config.from_static_path('/v4/static/v1.9.7-fc2ddc')
            Config.register_patrol('/v4/static/v1.9.7-fc2ddc', cfg._replace(lib_key='x'))
        """
        cls._patrols[cls._ver(static_path)] = patrol

    @classmethod
    def from_static_path(cls, static_path: str | None) -> Patrol:
        """Resolve the patrol values of the build a site is serving.

        ``static_path`` comes from the ``/load`` response, e.g.
        ``/v4/static/v1.9.7-fc2ddc``. Each ``data/*.json`` is read at most once.
        There is deliberately no fallback: values from another build are rejected
        by the server with an opaque failure.
        """
        ver = cls._ver(static_path)
        # Must stay in sync with the /^(v?\d+\.\d+\.\d+)/ in scripts/extract-config.mjs.
        major = re.match(r'v?\d+\.\d+\.\d+', ver)
        if major is None:
            raise ConfigError(f'unsupported static_path: {static_path!r}')

        name = f'{major[0]}-config.json'
        if ver not in cls._patrols:
            cls._load(name)
        patrol = cls._patrols.get(ver)
        if patrol is None:
            raise ConfigError(f'no config for {ver} in {name}')
        return patrol

    @classmethod
    def _load(cls, name: str) -> None:
        path = files('wulu_geetest_bypass').joinpath('data', name)
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except OSError as e:
            raise ConfigError(f'{name} is unreadable: {e}') from e
        except ValueError as e:
            raise ConfigError(f'{name} is not valid JSON') from e
        if not isinstance(raw, dict):
            raise ConfigError(f'{name} is not a JSON object')

        try:
            # setdefault, so an entry registered by the user survives the file load.
            for ver, entry in raw.items():
                cls._patrols.setdefault(ver, Patrol(**entry))
        except TypeError as e:
            raise ConfigError(f'{name} has a malformed entry: {e}') from e
