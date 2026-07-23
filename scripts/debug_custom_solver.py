import asyncio
from pathlib import Path

from wulu_geetest_bypass import Geetest

OUT = Path('resources/solver_debug')

SOLVER_SIGNATURES = {
    'icon':   '(imgs: bytes, ques: list[bytes]) -> list[list[int]]',
    'word':   '(imgs: bytes, ques: list[bytes]) -> list[list[int]]',
    'nine':   '(imgs: bytes, ques: list[bytes], nine_nums: int) -> list[list[int]]',
    'phrase': '(imgs: bytes) -> list',
    'space':  '(imgs: bytes) -> list',
    'pencil': '(imgs: bytes) -> list',
    'voice':  '(voice_audio: bytes) -> list',
    'slide':  '(bg: bytes, slice: bytes, ypos: int) -> int',
}


def make_solver(risk_type: str):
    sig = SOLVER_SIGNATURES[risk_type]

    if risk_type in ('icon', 'word'):
        def solver(imgs, ques):
            out = OUT / risk_type
            out.mkdir(parents=True, exist_ok=True)
            print(f'  imgs: {type(imgs).__name__} len={len(imgs)}')
            print(f'  ques: list[{len(ques)}]')
            for i, q in enumerate(ques):
                print(f'    [{i}] {type(q).__name__} len={len(q)}')
                (out / f'ques_{i}.png').write_bytes(q)
            (out / 'imgs.png').write_bytes(imgs)
            return [[10, 20], [30, 40]]
        return solver

    if risk_type == 'nine':
        def solver(imgs, ques, nine_nums):
            out = OUT / risk_type
            out.mkdir(parents=True, exist_ok=True)
            print(f'  imgs: {type(imgs).__name__} len={len(imgs)}')
            print(f'  ques: list[{len(ques)}]')
            for i, q in enumerate(ques):
                print(f'    [{i}] {type(q).__name__} len={len(q)}')
                (out / f'ques_{i}.png').write_bytes(q)
            (out / 'imgs.png').write_bytes(imgs)
            print(f'  nine_nums: {nine_nums} {type(nine_nums).__name__}')
            return [[1, 1], [2, 2]]
        return solver

    if risk_type in ('phrase', 'space', 'pencil'):
        def solver(imgs):
            out = OUT / risk_type
            out.mkdir(parents=True, exist_ok=True)
            print(f'  imgs: {type(imgs).__name__} len={len(imgs)}')
            (out / 'imgs.png').write_bytes(imgs)
            return [[10, 20], [30, 40]]
        return solver

    if risk_type == 'voice':
        def solver(voice_audio):
            out = OUT / risk_type
            out.mkdir(parents=True, exist_ok=True)
            print(f'  voice_audio: {type(voice_audio).__name__} len={len(voice_audio)}')
            (out / 'audio.mp3').write_bytes(voice_audio)
            return 'dummy'
        return solver

    if risk_type == 'slide':
        def solver(bg, sl, ypos):
            out = OUT / risk_type
            out.mkdir(parents=True, exist_ok=True)
            print(f'  bg:    {type(bg).__name__} len={len(bg)}')
            print(f'  slice: {type(sl).__name__} len={len(sl)}')
            print(f'  ypos:  {ypos} {type(ypos).__name__}')
            (out / 'bg.png').write_bytes(bg)
            (out / 'slice.png').write_bytes(sl)
            return 120
        return solver


async def test_one(risk_type: str):
    print(f'\n=== {risk_type} ===')
    print(f'  expected: {SOLVER_SIGNATURES[risk_type]}')

    Geetest.register_solver(risk_type, make_solver(risk_type))
    g = Geetest(captcha_id='54088bb07d2df3c46b79f80300b0abbe', risk_type=risk_type)
    try:
        result = await g.resolve()
        print(f'  result: {result}')
    except NotImplementedError as e:
        print(f'  NOT_IMPLEMENTED: {e}')
    except Exception as e:
        print(f'  {type(e).__name__}: {e}')


async def main():
    for rt in ['icon', 'word', 'nine', 'phrase', 'pencil', 'voice', 'slide']:
        await test_one(rt)


asyncio.run(main())
