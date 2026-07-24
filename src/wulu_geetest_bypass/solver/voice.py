import miniaudio
import numpy as np
from wulu_geetest_bypass_voice import load_templates

from .._exceptions import VerifyError

_cache: dict[str, tuple[np.ndarray, np.ndarray, int, str, np.ndarray]] = {}
_prompts: dict[str, np.ndarray] | None = None
_mel_basis = None
_dct_mat = None


def _load_audio(data: bytes, sr: int = 16000) -> np.ndarray:
    decoded = miniaudio.decode(
        data,
        output_format=miniaudio.SampleFormat.FLOAT32,
        sample_rate=sr,
    )
    audio = np.frombuffer(decoded.samples, dtype=np.float32)
    if decoded.nchannels > 1:
        audio = audio.reshape(-1, decoded.nchannels).mean(axis=1)
    return audio


def _stft(y: np.ndarray, n_fft: int = 2048, hop_length: int = 512) -> np.ndarray:
    y_pad = np.pad(y, n_fft // 2, mode='reflect')
    n_frames = 1 + (len(y_pad) - n_fft) // hop_length
    if n_frames <= 0:
        return np.zeros((1 + n_fft // 2, 1), dtype=complex)
    frames = np.lib.stride_tricks.as_strided(
        y_pad,
        shape=(n_frames, n_fft),
        strides=(y_pad.itemsize * hop_length, y_pad.itemsize),
    )
    window = np.hanning(n_fft).astype(np.float32)
    return np.fft.rfft((frames * window).astype(np.float32), axis=1).T


def _create_mel_filterbank(sr: int, n_fft: int, n_mels: int = 128) -> np.ndarray:
    fmax = sr / 2.0
    mel_max = 2595.0 * np.log10(1.0 + fmax / 700.0)
    mels = np.linspace(0, mel_max, n_mels + 2)
    hz = 700.0 * (10.0 ** (mels / 2595.0) - 1.0)
    fft_bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    filters = np.zeros((n_mels, int(1 + n_fft // 2)))
    for i in range(n_mels):
        for j in range(fft_bins[i], fft_bins[i + 1]):
            filters[i, j] = (j - fft_bins[i]) / (fft_bins[i + 1] - fft_bins[i])
        for j in range(fft_bins[i + 1], fft_bins[i + 2]):
            filters[i, j] = (fft_bins[i + 2] - j) / (fft_bins[i + 2] - fft_bins[i + 1])
    return filters


def _dct_matrix(n_filters: int, n_ceps: int = 13) -> np.ndarray:
    n = np.arange(n_filters)
    k = np.arange(n_ceps)[:, np.newaxis]
    mat = np.cos(np.pi * k * (2 * n + 1) / (2 * n_filters))
    mat[0] /= np.sqrt(2)
    return mat * np.sqrt(2 / n_filters)


def _compute_mfcc(y: np.ndarray, sr: int = 16000, n_mfcc: int = 13) -> np.ndarray:
    global _mel_basis, _dct_mat
    n_fft, hop_length, n_mels = 2048, 512, 128
    if len(y) == 0:
        return np.zeros((n_mfcc, 1), dtype=np.float32)
    S = np.abs(_stft(y, n_fft, hop_length).astype(np.complex64)) ** 2
    if _mel_basis is None:
        _mel_basis = _create_mel_filterbank(sr, n_fft, n_mels).astype(np.float32)
    mel_S = np.dot(_mel_basis, S)
    log_mel_S = 10.0 * np.log10(np.maximum(1e-10, mel_S))
    if _dct_mat is None:
        _dct_mat = _dct_matrix(n_mels, n_mfcc).astype(np.float32)
    return np.dot(_dct_mat, log_mel_S).astype(np.float32)


def _compute_delta(x: np.ndarray, order: int = 1, width: int = 9) -> np.ndarray:
    half = (width - 1) // 2
    pad = np.pad(x, ((0, 0), (half, half)), mode='edge')
    d = np.zeros_like(x)
    norm = 2 * sum(i**2 for i in range(1, half + 1))
    for i in range(1, half + 1):
        d += i * (
            pad[:, half + i : half + i + x.shape[1]]
            - pad[:, half - i : half - i + x.shape[1]]
        )
    d /= norm
    if order == 2:
        return _compute_delta(d, order=1, width=width)
    return d


def _split_by_silence(y: np.ndarray, sr: int) -> list[np.ndarray]:
    if len(y) == 0:
        return []
    hop_length = int(sr * 0.01)
    frame_length = 2048
    top_db = 35
    min_samples = int(sr * 0.05)
    min_energy = 0.02
    pad_len = frame_length // 2
    y_pad = np.pad(y, pad_len, mode='constant')
    n_frames = 1 + (len(y_pad) - frame_length) // hop_length
    if n_frames <= 0:
        return [y] if len(y) >= min_samples else []
    frames = np.lib.stride_tricks.as_strided(
        y_pad,
        shape=(n_frames, frame_length),
        strides=(y_pad.itemsize * hop_length, y_pad.itemsize),
    )
    rms = np.sqrt(np.mean(frames**2, axis=1))
    rms_db = 20 * np.log10(np.maximum(rms, 1e-10))
    threshold = np.max(rms_db) - top_db
    is_speech = rms_db > threshold
    padded = np.pad(is_speech, (1, 1), mode='constant')
    changes = np.diff(padded.astype(int))
    starts = np.where(changes == 1)[0] * hop_length
    ends = np.where(changes == -1)[0] * hop_length

    min_silence = int(sr * 0.18)
    if len(starts) > 1:
        ms, me = [starts[0]], []
        for i in range(1, len(starts)):
            if starts[i] - ends[i - 1] < min_silence:
                continue
            me.append(ends[i - 1])
            ms.append(starts[i])
        me.append(ends[-1])
        starts, ends = np.array(ms), np.array(me)

    segs = [y[s:e] for s, e in zip(starts, ends) if e - s >= min_samples]
    segs = [s for s in segs if np.sqrt(np.mean(s**2)) >= min_energy]
    return segs


def _load_one(lang: str):
    if lang not in _cache:
        X, y, sr, lang_name, prompt = load_templates(lang)
        if _prompts is not None:
            _prompts[lang] = prompt
        _cache[lang] = (X, y, sr, lang_name, prompt)


def _load_all():
    global _prompts
    if _prompts is not None:
        return
    _prompts = {}
    for lang in ('zho', 'eng'):
        _load_one(lang)
        _prompts[lang] = _cache[lang][4]


def _detect_lang(prompt_feat: np.ndarray) -> str:
    _load_all()
    best_lang = 'zho'
    best_dist = float('inf')
    for lang, p in _prompts.items():
        dist = np.linalg.norm(prompt_feat - p)
        if dist < best_dist:
            best_dist = dist
            best_lang = lang
    return best_lang


def _predict(feat: np.ndarray, centroids: np.ndarray, labels: np.ndarray) -> int:
    dists = np.linalg.norm(centroids - feat, axis=1)
    return labels[dists.argmin()]


def _mfcc_feature(seg: np.ndarray, sr: int) -> np.ndarray:
    m = _compute_mfcc(seg, sr=sr, n_mfcc=13)
    d = _compute_delta(m, order=1)
    d2 = _compute_delta(m, order=2)
    return np.concatenate([m.mean(axis=1), d.mean(axis=1), d2.mean(axis=1)])


def solve_voice(mp3_bytes: bytes, lang: str = '') -> str:
    sr = 16000
    audio = _load_audio(mp3_bytes, sr)
    segs = _split_by_silence(audio, sr)
    if len(segs) != 7:
        raise VerifyError(
            f'voice segmentation failed: expected 7 segments (prompt + 6 digits), got {len(segs)}'
        )
    if lang:
        _load_one(lang)
        centroids, labels, _, _, _ = _cache[lang]
    else:
        prompt_feat = _mfcc_feature(segs[0], sr)
        lang = _detect_lang(prompt_feat)
        centroids, labels, _, _, _ = _cache[lang]
    digits = []
    for seg in segs[1 : 1 + 6]:
        feat = _mfcc_feature(seg, sr)
        pred = _predict(feat, centroids, labels)
        digits.append(str(pred))
    return ''.join(digits)
