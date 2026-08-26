import importlib.metadata

from wulu_geetest_bypass import Geetest
from wulu_geetest_bypass.solver import discover_plugins


def _fake_entry_point(name, load_func):
    class _FakeEntryPoint:
        def load(self):
            return load_func

    _FakeEntryPoint.name = name
    return _FakeEntryPoint()


def test_discover_plugins_empty(monkeypatch):
    monkeypatch.setattr(
        importlib.metadata,
        'entry_points',
        lambda group: [],
    )
    discover_plugins.cache_clear()
    assert discover_plugins() == {}
    discover_plugins.cache_clear()


def test_discover_plugins_loads(monkeypatch):
    def fake_solver(*args, **kwargs):
        return (0, (1, 1))

    monkeypatch.setattr(
        importlib.metadata,
        'entry_points',
        lambda group: [
            _fake_entry_point('icon', fake_solver),
            _fake_entry_point('word', fake_solver),
        ],
    )
    discover_plugins.cache_clear()
    plugins = discover_plugins()
    assert set(plugins) == {'icon', 'word'}
    assert plugins['icon'](1, 2) == (0, (1, 1))
    discover_plugins.cache_clear()


def test_discover_plugins_skips_broken(monkeypatch):
    class _BrokenEntryPoint:
        name = 'broken'

        def load(self):
            raise ImportError('missing dep')

    monkeypatch.setattr(
        importlib.metadata,
        'entry_points',
        lambda group: [_BrokenEntryPoint()],
    )
    discover_plugins.cache_clear()
    assert discover_plugins() == {}
    discover_plugins.cache_clear()


def test_plugins_merged_into_solvers(monkeypatch):
    def fake_solver(*args, **kwargs):
        return 42

    monkeypatch.setattr(
        importlib.metadata,
        'entry_points',
        lambda group: [_fake_entry_point('icon', fake_solver)],
    )
    discover_plugins.cache_clear()
    Geetest._solvers.update(discover_plugins())
    # pyrefly: ignore [bad-argument-count, bad-argument-type, missing-argument]
    assert Geetest._solvers['icon'](1) == 42
    Geetest._solvers.pop('icon', None)
    discover_plugins.cache_clear()


def test_entry_point_group_name():
    from wulu_geetest_bypass.solver import _ENTRY_POINT_GROUP

    assert _ENTRY_POINT_GROUP == 'wulu_geetest_bypass.solvers'
