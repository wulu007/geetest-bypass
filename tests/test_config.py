import pytest

import wulu_geetest_bypass.config as config_mod
from wulu_geetest_bypass._exceptions import ConfigError
from wulu_geetest_bypass.config import Config, Patrol

CUSTOM = Patrol('1', 'AAAA', 'bbbb', '(n[0:1])', 'n[0:1]', False)


@pytest.fixture(autouse=True)
def _fresh_registry():
    """``_patrols`` is class state and would otherwise leak between tests."""
    Config._patrols.clear()
    yield
    Config._patrols.clear()


def test_resolves_recorded_builds():
    # Both entries live in data/v1.9.7-config.json and must not be confused with each other.
    assert Config.from_static_path('/v4/static/v1.9.7-fc2ddc').lib_key == 'd4tf'
    assert Config.from_static_path('/v4/static/v1.9.7-0ad79a').lib_key == 'dQFB'


def test_rejects_unrecorded_build():
    # v1.9.7-config.json is readable -- it just does not record this build.
    with pytest.raises(ConfigError, match='no config for v1.9.7-abc123'):
        Config.from_static_path('/v4/static/v1.9.7-abc123')


def test_rejects_unreleased_version():
    # No config file at all: a build newer than the daily job's last run.
    with pytest.raises(ConfigError, match='unreadable'):
        Config.from_static_path('/v4/static/v9.9.9-deadbe')


def test_rejects_unusable_static_path():
    for bad in (None, '', '/v4/static/', 'nonsense'):
        with pytest.raises(ConfigError):
            Config.from_static_path(bad)


def test_reads_each_build_file_once(monkeypatch):
    reads = []
    real_files = config_mod.files
    monkeypatch.setattr(
        config_mod, 'files', lambda pkg: (reads.append(pkg), real_files(pkg))[1]
    )

    Config.from_static_path('/v4/static/v1.9.7-fc2ddc')
    Config.from_static_path('/v4/static/v1.9.7-0ad79a')
    assert reads == ['wulu_geetest_bypass']


def test_registered_patrol_wins_over_file():
    Config.from_static_path('/v4/static/v1.9.7-fc2ddc')  # file wins first...
    Config.register_patrol('/v4/static/v1.9.7-fc2ddc', CUSTOM)
    assert Config.from_static_path('/v4/static/v1.9.7-fc2ddc') is CUSTOM


def test_registered_patrol_survives_file_load():
    Config.register_patrol('/v4/static/v1.9.7-fc2ddc', CUSTOM)  # ...or registers first
    Config.from_static_path('/v4/static/v1.9.7-0ad79a')  # triggers the file load
    assert Config.from_static_path('/v4/static/v1.9.7-fc2ddc') is CUSTOM


def test_registered_patrol_covers_unrecorded_build():
    Config.register_patrol('/v4/static/v9.9.9-zz', CUSTOM)
    assert Config.from_static_path('/v4/static/v9.9.9-zz') is CUSTOM
