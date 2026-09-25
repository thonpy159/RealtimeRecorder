import numpy as np
from app.audio.quality import stationary_broadband_noise


def test_stationary_noise_at_different_levels():
    noise = np.random.default_rng(91).normal(size=48000).astype(np.float32)
    assert stationary_broadband_noise(noise * .003)
    assert stationary_broadband_noise(noise * .03)


def test_quiet_voiced_sound_and_short_interjection_are_preserved():
    t = np.arange(32000) / 16000
    vowel = (.002 * np.sin(2*np.pi*180*t) + .001*np.sin(2*np.pi*360*t)).astype(np.float32)
    assert not stationary_broadband_noise(vowel)
    assert not stationary_broadband_noise(np.random.default_rng(92).normal(0,.003,4000))


def test_changing_unvoiced_energy_is_preserved():
    noise = np.random.default_rng(93).normal(0,.01,32000).astype(np.float32)
    noise[8000:16000] *= .05
    noise[24000:] *= .05
    assert not stationary_broadband_noise(noise)


def test_noise_with_vad_padding_but_not_padded_voiced_speech():
    noise = np.random.default_rng(94).normal(0,.003,8000).astype(np.float32)
    assert stationary_broadband_noise(np.pad(noise,(8000,4000)))
    t = np.arange(8000)/16000
    voiced = (.003*np.sin(2*np.pi*200*t)).astype(np.float32)
    assert not stationary_broadband_noise(np.pad(voiced,(8000,4000)))
