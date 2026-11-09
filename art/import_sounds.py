"""Turns downloaded sound clips into the site's prank sounds: trims the silence, cuts long ones short,
fades the end, levels the loudness to match the others and saves sounds/<prank>.wav.
The downloads stay in art/sound-sources/ so this can be run again.  Needs PyAV, numpy and scipy.

Usage:  python art/import_sounds.py
"""
import os

import av
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "art", "sound-sources")
OUT = os.path.join(HERE, "sounds")
SR = 32000

# prank -> (downloaded file, longest it may last in seconds)
CLIPS = {
    "fart": ("dry-fart.mp3", 2),
    "fahhh": ("fahhh_KcgAXfs.mp3", 2.5),
    "kiss": ("quick-kiss.mp3", 1),
    "hearts": ("love-impact.mp3", 1.5),
    "crown": ("ta-da_yrvBrlS.mp3", 1.8),
    "whoosh": ("whoosh-wind.mp3", 0.6),
    "booing": ("booing-from-crowd_uhGsVPW.mp3", 1.1),
    "boo": ("phasmophobia-ghost-attack-1_b6tVbw6.mp3", 2.6),
    "goldfish": ("pain_I8lLPWS.mp3", 1.5),
}


def decode(path):
    c = av.open(path)
    s = c.streams.audio[0]
    parts = []
    for fr in c.decode(s):
        a = fr.to_ndarray().astype(np.float32)
        if a.dtype.kind == "i" or np.abs(a).max() > 1.5:
            a = a / 32768
        # planar frames come as (channels, n); packed stereo as (1, n*channels)
        if a.ndim == 2 and a.shape[0] == s.channels:
            a = a.mean(0)
        elif s.channels > 1:
            a = a.reshape(-1, s.channels).mean(1)
        parts.append(a.reshape(-1))
    return np.concatenate(parts), s.rate


def prepare(x, sr, longest, loud=0.16, peak=0.89):
    x = resample_poly(x, SR, sr) if sr != SR else x
    on = np.where(np.abs(x) > np.abs(x).max() * 0.02)[0]
    x = x[max(0, on[0] - int(0.01 * SR)): on[-1] + int(0.05 * SR)]       # trim silence at both ends
    if len(x) > longest * SR:
        x = x[: int(longest * SR)]
        fade = int(min(0.35, longest / 3) * SR)                            # a cut-short clip fades out
        x[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    fade_in = int(0.004 * SR)
    x[:fade_in] *= np.linspace(0, 1, fade_in)
    x[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    body = x[np.abs(x) > np.abs(x).max() * 0.05]
    x = x / (np.sqrt(np.mean(body ** 2)) + 1e-9) * loud                    # same loudness as the rest
    return np.tanh(x / peak) * peak


if __name__ == "__main__":
    for name, (file, longest) in CLIPS.items():
        x, sr = decode(os.path.join(SRC, file))
        y = prepare(x, sr, longest)
        for ext in ("mp3", "ogg"):  # a finished .wav is what the site plays
            stale = os.path.join(OUT, f"{name}.{ext}")
            if os.path.exists(stale):
                os.remove(stale)
        wavfile.write(os.path.join(OUT, name + ".wav"), SR, (y * 32767).astype(np.int16))
        print(f"{name:9} <- {file:42} {len(y) / SR:.2f}s")
