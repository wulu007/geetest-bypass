import base64
import re
from itertools import pairwise

from wulu_geetest_bypass.track import (
    _PERCENT_PRECISION,
    TrackBuilder,
    track_unzip,
    track_zip,
)

test_data = {
    'm': 1,
    'w': 300.015625,
    'h': 261.5234375,
    's': 1787473447410,
    'e': 1787473672905,
    'p': [
        [0, 0.0105, 0.5232, 0],
        [87, 0.214, 0.5273, 1],
        [112, 0.2316, 0.5313, 1],
        [152, 0.2316, 0.5393, 1],
        [175, 0.2244, 0.5591, 1],
        [200, 0.2166, 0.5732, 1],
        [224, 0.2043, 0.5999, 1],
        [247, 0.1938, 0.632, 1],
        [271, 0.1812, 0.6777, 1],
        [296, 0.1603, 0.7316, 1],
        [319, 0.14, 0.7612, 1],
        [343, 0.1367, 0.7839, 1],
        [367, 0.1333, 0.7915, 1],
        [38184, 0.1267, 0.7953, 1],
        [141905, 0.1267, 0.7953, 1],
        [145118, 0.02, 0.998, 1],
        [145135, 0.0267, 0.9827, 1],
        [145153, 0.0367, 0.9636, 1],
        [145175, 0.0467, 0.9406, 1],
        [145206, 0.0567, 0.9177, 1],
        [145230, 0.06, 0.9024, 1],
        [145254, 0.0633, 0.8948, 1],
        [145382, 0.07, 0.8871, 1],
        [145502, 0.0767, 0.8871, 1],
        [214366, 0.0767, 0.8871, 3],
        [219229, 0, 0.8603, 1],
        [219253, 0.0567, 0.868, 1],
        [219277, 0.0933, 0.868, 1],
        [219301, 0.1233, 0.868, 1],
        [219318, 0.1433, 0.868, 1],
        [219335, 0.16, 0.8642, 1],
        [219352, 0.1733, 0.8642, 1],
        [219373, 0.18, 0.8642, 1],
        [219493, 0.1867, 0.8642, 1],
        [219519, 0.1933, 0.8642, 1],
        [219543, 0.22, 0.8642, 1],
        [219565, 0.2633, 0.8642, 1],
        [219589, 0.3, 0.8642, 1],
        [219613, 0.3167, 0.8603, 1],
        [219637, 0.34, 0.8565, 1],
        [219661, 0.37, 0.8527, 1],
        [219684, 0.3933, 0.8489, 1],
        [219701, 0.4066, 0.845, 1],
        [219726, 0.4166, 0.845, 1],
        [219749, 0.4333, 0.845, 1],
        [219773, 0.45, 0.845, 1],
        [219797, 0.4733, 0.8412, 1],
        [219821, 0.4933, 0.8412, 1],
        [219845, 0.5033, 0.8412, 1],
        [219868, 0.5133, 0.8412, 1],
        [219885, 0.52, 0.8412, 1],
        [219909, 0.5266, 0.8412, 1],
        [219942, 0.5366, 0.8374, 1],
        [219965, 0.5466, 0.8374, 1],
        [219989, 0.5566, 0.8336, 1],
        [220021, 0.5633, 0.8336, 1],
        [220061, 0.57, 0.8336, 1],
        [220093, 0.5766, 0.8298, 1],
        [220134, 0.5833, 0.8298, 1],
        [220157, 0.59, 0.8298, 1],
        [220189, 0.5966, 0.8298, 1],
        [220230, 0.6033, 0.8298, 1],
        [220260, 0.61, 0.8298, 1],
        [220285, 0.6166, 0.8259, 1],
        [220343, 0.6233, 0.8259, 1],
        [220381, 0.63, 0.8259, 1],
        [220413, 0.6366, 0.8259, 1],
        [225495, 0.64, 0.8259, 2],
    ],
}


test_zip_data = 'H4sIADCximoAA22Usc7bMAyE38Wz8UOkREnMqwQZC3QpUKBDh6Lv3jtScRynU-LvaPJEUv6z_dhusm-_t1st5auIdbV9-77dtMuXaW114PkXgsYcbdTWRpOyb98O0od6QczP7Xa_l51J8Fj4su7lsd_nwJNKCzbqLmAi0L60Sietsqi9UV8UDkC1RQZzCaqFtVR6xA7UCqoM0tIqqbsnbbQgXid--jN0COEMJ32MkdSZT3phgkEnpFWclLlHxwvBoobg_KSzZql8lFrjfRdLOmXyZdGMdltHa8Le_U8wEbotdOc-D1oZXjLcp6ZrCngTQtb3XtM4hWhfaSm0cgiKvxAsBVkNoFBjjFS9oKFPbDxC6XG06e3wVCdNFqaZE11d2MJ7GZH_ELAINWZ2FmoIroo2k7H9Geya50qXs2dRcvgF93Tz4rXEWPWDRztR_MqjobFxs7e1GsCxijJW-EnABnNtLrhhWYmXzZdguTpPnych9kdZ5g332PbV5bMwmehKO64OqKy6r771SlI5ssmcT9zZntAmbuOBYz1x4yJ_Q6kljGgntiYa1I48QwlaXr8zb3SJLmeiF4-24fmdOo3gI5LR62ZBmBpln35OQqSw8ilgpBBw867CzK_RBXuhUdN1gJOA5vLrk0Iduf8UYjLWPoWYjNkS1tVTfKHiFLZmeRZiChZTOONYIhuZSNethyAxR0PsVYgcxvpvOB1h2hchrzbW5JpIewi09YajeX2NWVFoCfn16-uanYXJHP2KW-wpPkuXRNY8KsSeEuvj8fcfNwgzzJYGAAA'


def _b64url_decode(encoded: str) -> bytes:
    return base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))


def test_track_zip_matches_fflate_container():
    """The gzip container must be byte-identical to fflate's ``gzipSync`` output.

    Only the deflate stream in between differs -- zlib and fflate are separate
    implementations (fflate needs 581 bytes here, zlib level 6 needs 541), and no
    zlib level / strategy / memLevel combination reproduces fflate's bytes.
    """
    captured = _b64url_decode(test_zip_data)
    mtime = int.from_bytes(captured[4:8], 'little')
    result = _b64url_decode(track_zip(test_data, mtime=mtime))

    assert result[:10] == captured[:10]  # magic, deflate, flags, mtime, XFL 0, OS 3
    assert result[-8:] == captured[-8:]  # crc32 + isize, i.e. identical json payload


def test_track_zip_encoding():
    encoded = track_zip(test_data)
    assert re.fullmatch(r'[A-Za-z0-9_-]+', encoded)  # urlsafe base64, unpadded


def test_track_zip_unzip():
    track_data = test_data
    unzipped = track_unzip(test_zip_data)
    assert unzipped == track_data
    assert track_unzip(track_zip(track_data)) == track_data


def test_gen_time():
    t = (
        TrackBuilder((0, 0))
        .move_to(0.345, 0.255, 700)
        .down()
        .move_to(0.5, 0.5, 400)
        .end()
        .build()
    )
    for i in t:
        print(i)
    print(f'len={len(t)}')
    stamps = [p[0] for p in t]
    assert len(stamps) > 2
    assert all(b > a for a, b in pairwise(stamps)), stamps
    for _, x, y, _track_type in t:
        assert x == round(x, _PERCENT_PRECISION)
        assert y == round(y, _PERCENT_PRECISION)


def test_gen_click_track():
    from wulu_geetest_bypass.track import TrackConfig, gen_click_track

    clicks = [(0.7483, 0.2174), (0.1417, 0.5472), (0.3050, 0.4473)]
    payload, duration = gen_click_track(clicks)

    assert duration == payload['e'] - payload['s']
    assert payload['m'] == 1
    assert payload['w'] == TrackConfig.click['w']
    assert payload['h'] == TrackConfig.click['h']
    assert duration > 0

    types = [e[3] for e in payload['p']]
    # 3 answers + 1 submit click, each DOWN followed by END
    assert types.count(3) == 4
    assert types.count(2) == 4

    img_w, img_h = TrackConfig.click['img_w'], TrackConfig.click['img_h']
    el_w, el_h = TrackConfig.click['w'], TrackConfig.click['h']
    expected = [(x * img_w / el_w, y * img_h / el_h) for x, y in clicks]

    downs = [e for e in payload['p'] if e[3] == 3]
    for (ex, ey), down in zip(expected, downs, strict=False):
        assert abs(down[1] - ex) <= TrackConfig.click['jitter'] + 0.01
        assert abs(down[2] - ey) <= TrackConfig.click['jitter'] + 0.01


def test_gen_click_track_no_submit():
    from wulu_geetest_bypass.track import gen_click_track

    payload, _ = gen_click_track([(0.1, 0.1)], with_submit=False)
    types = [e[3] for e in payload['p']]
    assert types.count(3) == 1
    assert types.count(2) == 1
