import numpy as np
from app.audio.preprocess import AudioPreprocessor


def tone(amplitude=.05, count=960, rate=48000):
    return (amplitude * np.sin(2 * np.pi * 400 * np.arange(count) / rate)).astype(np.float32)


def test_opposite_phase_microphone_does_not_cancel():
    x = tone(count=48000)
    stereo = np.column_stack((x, -x)).astype(np.float32)
    p = AudioPreprocessor(48000, 2, microphone=True)
    y = p.process(stereo, final=True)
    assert len(y) == 16000
    assert np.sqrt(np.mean(y * y)) > .03


def test_microphone_uses_non_silent_channel():
    x = tone(count=16000, rate=16000)
    p = AudioPreprocessor(16000, 2, microphone=True)
    y = p.process(np.column_stack((np.zeros_like(x), x)))
    assert p.selected_channel == 1 and np.max(np.abs(y)) >= .05


def test_quiet_voice_amplified_before_vad_without_clipping():
    p = AudioPreprocessor(16000, 1, microphone=True)
    x = tone(amplitude=.004, count=320, rate=16000)
    chunks = [p.process(x) for _ in range(10)]
    assert np.sqrt(np.mean(chunks[-1] ** 2)) > .02
    assert np.max(np.abs(chunks[-1])) <= 1
    assert p.gain <= 8


def test_silence_stays_silent_with_microphone_gain():
    p = AudioPreprocessor(16000, 1, microphone=True)
    for _ in range(50):
        assert np.count_nonzero(p.process(np.zeros(320, np.float32))) == 0


def test_loud_sound_after_quiet_sound_does_not_clip():
    p = AudioPreprocessor(16000, 1, microphone=True)
    for _ in range(10):
        p.process(tone(.004, 320, 16000))
    y = p.process(tone(.8, 320, 16000))
    assert np.max(np.abs(y)) < .96


def test_loopback_still_downmixes_stereo():
    p = AudioPreprocessor(16000, 2)
    x = np.array([[.2, .4], [.4, .2]], dtype=np.float32)
    np.testing.assert_allclose(p.process(x), [.3, .3])
