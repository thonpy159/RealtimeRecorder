import numpy as np
import soxr


class AudioPreprocessor:
    """Stateful band-limited resampling; phase/filter history survives chunks."""
    def __init__(self, sample_rate, channels, microphone=False):
        if sample_rate <= 0 or channels < 1:
            raise ValueError('Invalid audio format')
        self.channels = channels
        self.microphone = microphone
        self.channel_power = np.zeros(channels, dtype=np.float32)
        self.selected_channel = 0
        self.gain = 1.0
        self.raw_rms = 0.0
        self.raw_peak = 0.0
        self.resampler = (soxr.ResampleStream(sample_rate, 16000, 1, dtype='float32', quality='HQ')
                          if sample_rate != 16000 else None)

    def process(self, pcm, final=False):
        x = np.frombuffer(pcm, dtype=np.float32) if isinstance(pcm, bytes) else np.asarray(pcm, dtype=np.float32)
        x = x.reshape(-1, self.channels)
        if not len(x):
            return self.resampler.resample_chunk(np.empty(0, np.float32), last=final) if self.resampler is not None else np.empty(0, np.float32)
        x = np.clip(np.nan_to_num(x), -1, 1)
        if self.microphone and self.channels > 1:
            # Microphone channels can be duplicated with opposite phase, or one
            # channel can be silent. Averaging can destroy the speech waveform.
            power = np.mean(x * x, axis=0)
            self.channel_power = .8 * self.channel_power + .2 * power
            strongest = int(np.argmax(self.channel_power))
            if self.channel_power[strongest] > 2 * self.channel_power[self.selected_channel]:
                self.selected_channel = strongest
            x = x[:, self.selected_channel]
        else:
            x = x.mean(axis=1, dtype=np.float32)
        self.raw_rms = float(np.sqrt(np.mean(x * x)))
        self.raw_peak = float(np.max(np.abs(x)))
        if self.microphone:
            # Bounded gain before VAD is essential: post-ASR normalization cannot
            # recover a word the VAD already discarded as too quiet.
            target = min(8., max(1., .045 / max(self.raw_rms, .0001)))
            target = min(target, .95 / max(self.raw_peak, .0001))
            next_gain = target if target < self.gain else .4 * target + .6 * self.gain
            x = x * np.linspace(min(self.gain, next_gain), next_gain, len(x), dtype=np.float32)
            self.gain = next_gain
        x = np.clip(np.nan_to_num(x), -1, 1)
        if self.resampler is not None:
            x = self.resampler.resample_chunk(x, last=final)
        return np.ascontiguousarray(x, dtype=np.float32)
