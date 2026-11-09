"""Makes the prank sound effects. Offline tool: the site only plays the files it writes to sounds/.

Every sound is built from scratch (filtered noise, formant filters, layered hits), so there are no
third-party recordings to license. Run:  python art/sounds.py   (needs numpy and scipy)
To use your own recording instead, drop a .wav with the same name into sounds/.
"""
import os

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, sosfilt

SR = 32000
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds")
rng = np.random.default_rng(7)


def t(sec):
    return np.arange(int(sec * SR)) / SR


def noise(sec):
    return rng.standard_normal(int(sec * SR))


def band(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)


def low(x, f, order=2):
    return sosfilt(butter(order, f, "lowpass", fs=SR, output="sos"), x)


def high(x, f, order=2):
    return sosfilt(butter(order, f, "highpass", fs=SR, output="sos"), x)


def reso(x, f, q):
    """A resonant peak (a formant) at f Hz."""
    w = 2 * np.pi * f / SR
    r = np.exp(-np.pi * (f / q) / SR)
    return lfilter([1 - r], [1, -2 * r * np.cos(w), r * r], x)


def env(n, attack, decay, sustain=0.0):
    """attack then exponential decay, as a curve of n samples."""
    a = int(attack * SR)
    e = np.exp(-np.arange(n) / max(1, decay * SR)) * (1 - sustain) + sustain
    if a:
        e[:a] *= np.linspace(0, 1, a)
    return e


def at(total, sec, x, start):
    i = int(start * SR)
    j = min(len(total), i + len(x))
    total[i:j] += x[: j - i]


def glottal(freq):
    """A voice-like buzz whose pitch follows the freq curve (one value per sample)."""
    phase = np.cumsum(freq) / SR
    saw = 2 * (phase % 1) - 1
    return saw - np.convolve(saw, np.ones(3) / 3, "same") * 0.3


def reverb(x, room=0.25, mix=0.25):
    """A small, cheap room so the sounds don't feel dry."""
    ir = noise(room) * np.exp(-t(room) / (room / 5))
    ir = low(ir, 3200)
    wet = np.convolve(x, ir)[: len(x) + int(room * SR)]
    out = np.zeros(len(wet))
    out[: len(x)] += x
    return out + wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max() * mix * 0.7


def save(name, x, loud=0.16, peak=0.89):
    """Every sound comes out about as loud as the others: level by average loudness, then a soft
    limiter keeps the hits from clipping."""
    x = x - np.mean(x)
    fade = min(len(x), int(0.02 * SR))
    x[-fade:] *= np.linspace(1, 0, fade)
    body = x[np.abs(x) > np.abs(x).max() * 0.05]  # ignore the quiet tail when measuring
    x = x / (np.sqrt(np.mean(body ** 2)) + 1e-9) * loud
    x = np.tanh(x / peak) * peak
    os.makedirs(OUT, exist_ok=True)
    wavfile.write(os.path.join(OUT, name + ".wav"), SR, (x * 32767).astype(np.int16))
    print(f"{name}.wav  {len(x) / SR:.2f}s")


# ---------- the sounds ----------

def whoosh():
    d = 0.5
    x = noise(d)
    # a band of air that sweeps up as the thing flies past, then away
    sweep = 500 + 2600 * np.sin(np.pi * t(d) / d) ** 2
    y = np.zeros_like(x)
    for k in range(0, len(x), 512):
        seg = x[k:k + 512]
        f = sweep[k]
        y[k:k + 512] = band(np.concatenate([x[max(0, k - 256):k], seg]), f * 0.7, f * 1.4)[-len(seg):]
    return y * np.sin(np.pi * t(d) / d) ** 1.5


def fart():
    d = 1.1
    tt = t(d)
    # the pitch wanders and sags, with a few wet "flaps"
    f0 = 95 + 25 * np.sin(2 * np.pi * 3.1 * tt) + 18 * np.sin(2 * np.pi * 7.3 * tt + 1) - 30 * tt
    f0 += np.convolve(rng.standard_normal(len(tt)) * 40, np.ones(400) / 400, "same")
    buzz = glottal(np.clip(f0, 45, 160))
    rasp = noise(d) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * np.cumsum(f0) / SR)))
    x = 0.8 * buzz + 0.35 * rasp
    x = reso(x, 180, 4) * 1.4 + reso(x, 420, 6) + reso(x, 900, 8) * 0.4
    x = low(x, 1400)
    # flutter: the sound chokes on and off as it goes
    flutter = 0.6 + 0.4 * np.clip(np.sin(2 * np.pi * 11 * tt + np.sin(2 * np.pi * 2 * tt) * 3), 0, 1)
    e = env(len(tt), 0.02, 0.9) * (1 - np.exp(-tt * 40)) * flutter
    e[int(0.85 * SR):] *= np.linspace(1, 0, len(e) - int(0.85 * SR)) ** 2
    x = np.tanh(x * e * 3)
    return reverb(x, 0.2, 0.15)


def firecracker():
    d = 1.4
    out = np.zeros(int(d * SR))
    times = np.sort(rng.uniform(0, 0.55, 9))
    for i, s in enumerate(times):
        crack = high(noise(0.09), 1200) * env(int(0.09 * SR), 0.0005, 0.012)
        crack += band(noise(0.09), 300, 1500) * env(int(0.09 * SR), 0.001, 0.03) * 0.5
        at(out, d, crack * rng.uniform(0.5, 1.0), s)
    # the final bang: a sharp crack plus a low thump and its echo
    bang = high(noise(0.5), 500) * env(int(0.5 * SR), 0.0005, 0.05)
    thump = np.sin(2 * np.pi * np.cumsum(np.linspace(110, 45, int(0.5 * SR))) / SR) * env(int(0.5 * SR), 0.001, 0.12)
    at(out, d, bang * 1.6 + thump * 1.2, 0.62)
    out = np.tanh(out * 2.2)
    return reverb(out, 0.6, 0.35)


def balloon():
    d = 1.3
    out = np.zeros(int(d * SR))
    # the rubber bursts
    at(out, d, high(noise(0.05), 800) * env(int(0.05 * SR), 0.0003, 0.008) * 1.5, 0.0)
    # the water hits: a broad wet splash
    sp = band(noise(0.9), 600, 6000) * env(int(0.9 * SR), 0.004, 0.18)
    sp += low(noise(0.9), 400) * env(int(0.9 * SR), 0.002, 0.08) * 1.2
    at(out, d, sp, 0.01)
    # droplets: little rising plips
    for s in rng.uniform(0.12, 0.95, 14):
        n = int(0.04 * SR)
        f = np.linspace(rng.uniform(900, 1500), rng.uniform(1800, 3200), n)
        plip = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.012)
        at(out, d, plip * rng.uniform(0.15, 0.4), s)
    return reverb(out, 0.3, 0.2)


def curse():
    d = 2.2
    tt = t(d)
    # a cracked temple bell: inharmonic partials, slowly beating
    bell = sum(a * np.sin(2 * np.pi * f * tt + p) * np.exp(-tt * dec)
               for f, a, dec, p in [(196, 1, 1.4, 0), (199.5, .8, 1.5, 1), (512, .5, 2.5, 2), (1043, .3, 4, 0), (1561, .2, 5, 1)])
    # a low hum swells up under it
    hum = (np.sin(2 * np.pi * 58 * tt) + 0.6 * np.sin(2 * np.pi * 87.3 * tt)) * np.sin(np.pi * tt / d) ** 2
    # a breathy hiss, like a whisper
    hiss = band(noise(d), 2000, 6000) * np.sin(np.pi * np.clip(tt / 1.2, 0, 1)) ** 2 * 0.25
    return reverb(bell * env(len(tt), 0.003, 1.2) + hum * 0.5 + hiss, 0.9, 0.35)


def wet_slap(sec=0.12, lo=150, hi=2500, dec=0.025):
    n = int(sec * SR)
    return (band(noise(sec), lo, hi) * env(n, 0.0008, dec) + low(noise(sec), 250) * env(n, 0.001, dec * 2) * 0.8)


def goldfish():
    d = 1.3
    out = np.zeros(int(d * SR))
    at(out, d, wet_slap(0.2, 120, 3000, 0.04) * 1.6, 0.0)       # the slap
    for i, s in enumerate([0.32, 0.55, 0.74, 0.9]):              # flop, flop, flop
        at(out, d, wet_slap(0.09, 300, 2500, 0.015) * (0.7 - i * 0.12), s)
    return reverb(out, 0.25, 0.2)


def takoyaki():
    d = 1.0
    out = np.zeros(int(d * SR))
    for i, s in enumerate([0.0, 0.17, 0.3]):
        hit = wet_slap(0.25, 90, 1800, 0.05)
        squish = band(noise(0.25), 500, 2500) * env(int(0.25 * SR), 0.02, 0.06) * 0.4
        at(out, d, (hit + squish) * (1 - i * 0.15), s)
    return reverb(out, 0.25, 0.2)


def chime(freqs, gap, dec=1.2, bright=1.0):
    d = gap * len(freqs) + 1.5
    out = np.zeros(int(d * SR))
    for i, f in enumerate(freqs):
        tt = t(1.5)
        tone = sum(a * np.sin(2 * np.pi * f * m * tt) * np.exp(-tt * dec * m ** .5) for m, a in [(1, 1), (2.01, .4 * bright), (3.02, .2 * bright), (4.2, .1 * bright)])
        at(out, d, tone * env(len(tt), 0.002, 1.0), i * gap)
    return out


def hearts():
    out = chime([784, 988, 1175, 1568, 1976], 0.09, 2.2, 0.6)
    tt = t(len(out) / SR)
    shimmer = band(noise(len(out) / SR), 5000, 9000) * np.exp(-tt * 3) * 0.08
    return reverb(out + shimmer, 0.8, 0.4)


def crown():
    # a quick harp sweep up, then a bright "ta-da"
    out = chime([523, 659, 784, 1047, 1319, 1568, 2093], 0.045, 2.5, 0.8)
    tada = chime([1047, 1319, 1568], 0.0, 1.5, 1.0)
    at(out, len(out) / SR, tada * 0.9, 0.36)
    return reverb(out, 0.8, 0.35)


def vowel(f0, formants, d, breath=0.15, rasp=0.0):
    """A sung or shouted vowel: a buzz at pitch f0 (array) shaped by formant peaks."""
    src = glottal(f0) + noise(d) * breath
    if rasp:
        src += noise(d) * rasp * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * np.cumsum(f0) / SR)))
    return sum(reso(src, f, q) * g for f, q, g in formants)


def boo():
    d = 1.8
    tt = t(d)
    f0 = 210 - 70 * (tt / d) + 9 * np.sin(2 * np.pi * 5.5 * tt) * np.clip(tt * 2, 0, 1)
    oo = vowel(f0, [(330, 6, 1.4), (800, 8, 0.6), (2300, 10, 0.12)], d, breath=0.4)
    wind = band(noise(d), 300, 1200) * 0.35
    e = np.sin(np.pi * tt / d) ** 0.8
    return reverb((oo + wind) * e, 1.0, 0.45)


def chill():
    d = 1.8
    tt = t(d)
    wind = band(noise(d), 1500, 5000) * np.sin(np.pi * tt / d) ** 2 * 0.5
    out = wind
    for s in rng.uniform(0.05, 1.3, 9):
        f = rng.uniform(2500, 4800)
        n = int(0.5 * SR)
        tink = np.sin(2 * np.pi * f * t(0.5)) * env(n, 0.0005, 0.08) + np.sin(2 * np.pi * f * 2.7 * t(0.5)) * env(n, 0.0005, 0.03) * 0.4
        at(out, d, tink * rng.uniform(0.2, 0.5), s)
    return reverb(out, 0.9, 0.4)


def kiss():
    d = 0.9
    out = np.zeros(int(d * SR))
    # lips press, a little suction, then the smack
    suck = high(noise(0.08), 3000) * env(int(0.08 * SR), 0.03, 0.02) * 0.15
    at(out, d, suck, 0.0)
    smack = high(noise(0.03), 1500) * env(int(0.03 * SR), 0.0002, 0.004)
    pop = np.sin(2 * np.pi * np.cumsum(np.linspace(900, 300, int(0.03 * SR))) / SR) * env(int(0.03 * SR), 0.0002, 0.006)
    at(out, d, smack * 1.2 + pop, 0.08)
    # a cheeky "mwah"
    dd = 0.45
    tt = t(dd)
    f0 = 260 + 60 * np.sin(np.pi * tt / dd) - 80 * tt
    mwah = vowel(f0, [(280, 5, 1.0), (750, 7, 1.2), (1250, 9, .6), (2700, 12, .15)], dd, breath=0.08)
    mwah *= env(len(tt), 0.04, 0.25)
    mwah[: int(0.05 * SR)] *= np.linspace(0.2, 1, int(0.05 * SR))  # the "m" opening into "ah"
    at(out, d, mwah * 0.55, 0.12)
    return reverb(out, 0.3, 0.2)


def fahhh():
    """A long, fed-up "FAHHH": a breathy F that opens into a loud, cracking, falling AH."""
    d = 2.1
    out = np.zeros(int(d * SR))
    # the F: air pushed through the teeth
    f = high(noise(0.22), 1800) * env(int(0.22 * SR), 0.06, 0.2, 0.6)
    f[-int(0.06 * SR):] *= np.linspace(1, 0, int(0.06 * SR))
    at(out, d, f * 0.45, 0.0)
    # the AH: starts high and strained, slides down and runs out of breath
    dd = 1.85
    tt = t(dd)
    f0 = 210 + 40 * np.exp(-tt * 6) - 70 * (tt / dd) ** 1.6 + 5 * np.sin(2 * np.pi * 6 * tt) * (tt / dd)
    f0 += np.convolve(rng.standard_normal(len(tt)) * 6, np.ones(200) / 200, "same")  # a shaky voice
    ah = vowel(f0, [(800, 7, 1.3), (1200, 9, 1.0), (2600, 12, 0.45), (3400, 14, 0.2)], dd, breath=0.12, rasp=0.35)
    e = env(len(tt), 0.05, 2.5) * np.clip((dd - tt) / 0.5, 0, 1) ** 0.7
    ah = np.tanh(ah * e * 2.5)  # a shout, pushed a little past clean
    at(out, d, ah, 0.17)
    return reverb(out, 0.35, 0.18)


if __name__ == "__main__":
    for name, fn in [("whoosh", whoosh), ("fart", fart), ("firecracker", firecracker), ("balloon", balloon),
                     ("curse", curse), ("goldfish", goldfish), ("takoyaki", takoyaki), ("hearts", hearts),
                     ("crown", crown), ("boo", boo), ("chill", chill), ("kiss", kiss), ("fahhh", fahhh)]:
        save(name, fn())
