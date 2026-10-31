import asyncio

import pytest

from wulu_geetest_bypass import Geetest

test_risk = ['ai', 'slide', 'match', 'winlinze', 'svg_seed', 'svg_icon']


@pytest.mark.asyncio
@pytest.mark.parametrize('risk_type', test_risk)
async def test_risk_type(risk_type, cid):
    g = Geetest(captcha_id=cid, risk_type=risk_type)
    result = await g.resolve()
    assert result is not None


def test_tz_defaults_to_shanghai():
    assert Geetest(captcha_id='x').tz == {'name': 'Asia/Shanghai', 'offset': 480}


def test_tz_is_used_as_given():
    tz = {'name': 'America/New_York', 'offset': -240}
    assert Geetest(captcha_id='x', tz=tz).tz is tz


def test_auto_solve_icon_click():
    Geetest._solvers['icon'] = lambda imgs, ques: [(0.75, 0.2), (0.3, 0.5), (0.1, 0.8)]
    try:
        data = {
            'captcha_type': 'icon',
            'imgs': b'x',
            'ques': [b'a', b'b', b'c'],
        }
        # pyrefly: ignore[bad-argument-type]
        ans = Geetest.auto_solve(data)
        assert ans['userresponse'] == [[7500, 2000], [3000, 5000], [1000, 8000]]
        assert 'track' in ans and 'passtime' in ans
        assert ans['passtime'] > 0
    finally:
        del Geetest._solvers['icon']


@pytest.mark.asyncio
async def test_slide(cid):
    g = Geetest(captcha_id=cid, risk_type='slide')
    total = 50
    success = 0
    tasks = [g.resolve(1) for _ in range(total)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if not isinstance(r, Exception))
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f'Task {i} Error: {r}')
    print(f'Success: {success}/{total}')


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_slide_pass_rate(pass_rate):
    pytest.importorskip('cv2')
    from wulu_geetest_bypass.solver import solve_slide

    await pass_rate('slide', 0.9, lambda d: solve_slide(d['bg'], d['slice'], d['ypos']))


test_lang = [
    'ara',
    'deu',
    'eng',
    'fra',
    'ind',
    'jpn',
    'kor',
    'por',
    'rus',
    'spa',
    'zho-hk',
    'zho',
]


@pytest.mark.asyncio
@pytest.mark.parametrize('lang', test_lang)
async def test_voice(lang, cid):
    pytest.importorskip('miniaudio')
    pytest.importorskip('wulu_geetest_bypass_voice')
    g = Geetest(captcha_id=cid, risk_type='slide', lang=lang, voice=True)
    result = await g.resolve(1)
    assert result is not None


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_voice_pass_rate(pass_rate):
    pytest.importorskip('miniaudio')
    pytest.importorskip('wulu_geetest_bypass_voice')
    from wulu_geetest_bypass_voice import solve_voice

    await pass_rate(
        'slide',
        0.8,
        lambda d: solve_voice(
            d['voice_audio'],
            d['voice_path'].split('/')[-2],
            d['voice_path'].split('/')[-3],
        ),
        record_as='voice',
        voice=True,
    )


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_match_pass_rate(pass_rate):
    from wulu_geetest_bypass.solver import solve_match

    await pass_rate('match', 0.9, lambda d: solve_match(d['ques']))


@pytest.mark.accuracy
@pytest.mark.asyncio
async def test_winlinze_pass_rate(pass_rate):
    from wulu_geetest_bypass.solver import solve_winlinze

    await pass_rate('winlinze', 0.9, lambda d: solve_winlinze(d['ques']))


@pytest.mark.perf
def test_perf_solve_slide(benchmark):
    """离线基准：本地样本重复跑 solve_slide，warm 数据不含网络。"""
    pytest.importorskip('cv2')
    import json
    from pathlib import Path

    import numpy as np

    from wulu_geetest_bypass.solver import solve_slide

    root = (
        Path(__file__).resolve().parents[1]
        / 'resources'
        / 'solver_debug'
        / 'slide'
        / 'passed'
    )
    dirs = (
        sorted(p for p in root.iterdir() if (p / 'predicted.json').is_file())
        if root.is_dir()
        else []
    )
    if dirs:
        d = dirs[0]
        bg, sl = (d / 'bg.png').read_bytes(), (d / 'slice.png').read_bytes()
        ypos = json.loads((d / 'load.json').read_text(encoding='utf-8'))['ypos']
    else:  # 没有本地样本时用合成图，仅保证能量到耗时
        import cv2

        canvas = np.tile(np.arange(300, dtype=np.uint8), (200, 1))
        canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
        canvas[80:160, 120:200] = (90, 90, 90)
        tpl = np.full((80, 80, 4), 128, np.uint8)
        tpl[:, :, 3] = 255
        bg = cv2.imencode('.png', canvas)[1].tobytes()
        sl = cv2.imencode('.png', tpl)[1].tobytes()
        ypos = 80

    benchmark.extra_info['type'] = 'slide'
    res = benchmark(lambda: solve_slide(bg, sl, ypos))
    assert isinstance(res, int)


@pytest.mark.perf
def test_perf_solve_voice(benchmark):
    """离线基准：本地 mp3 重复跑 solve_voice（解码 + 分割 + MFCC + 模板匹配）。"""
    pytest.importorskip('miniaudio')
    pytest.importorskip('wulu_geetest_bypass_voice')
    from pathlib import Path

    from wulu_geetest_bypass_voice import solve_voice

    root = Path(__file__).resolve().parents[1] / 'resources' / 'voice' / 'raw'
    mp3s = sorted(root.glob('*.mp3')) if root.is_dir() else []
    if not mp3s:
        pytest.skip(f'no local sample under {root}')
    p = mp3s[0]
    lang = p.name.split('_')[0]
    audio = p.read_bytes()

    benchmark.extra_info['type'] = 'voice'
    res = benchmark(lambda: solve_voice(audio, lang, 'v4_voice_20261012'))
    assert isinstance(res, str)
