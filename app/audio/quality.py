"""Conservative rejection of sustained, stationary broadband noise."""
import numpy as np


def stationary_broadband_noise(audio):
    x = np.asarray(audio, dtype=np.float32)
    # Keep brief speech and interjections. This is not a loudness threshold.
    if x.ndim != 1 or len(x) < 12000:
        return False
    frames = x[:len(x) // 320 * 320].reshape(-1, 320)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    # VAD pre/post-roll includes quiet edges; retain internal pauses.
    active = np.flatnonzero(rms > max(float(np.median(rms)) * .1, 1e-7))
    if not len(active):
        return True
    frames = frames[active[0]:active[-1]+1]
    rms = rms[active[0]:active[-1]+1]
    if len(frames) < 15:
        return False
    # Speech pauses and changing syllables make energy nonstationary.
    if float(np.std(rms)) / max(float(np.mean(rms)), 1e-10) > .15:
        return False
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(320), n=512, axis=1)) ** 2
    band = spectrum[:, 10:240] + 1e-20  # 312.5 Hz .. 7.5 kHz
    flatness = np.exp(np.mean(np.log(band), axis=1)) / np.mean(band, axis=1)
    return bool(np.mean(flatness > .45) > .9)
