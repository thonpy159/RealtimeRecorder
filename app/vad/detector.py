import numpy as np
import sherpa_onnx


class SampleRing:
    def __init__(self, capacity):
        self.data = np.zeros(capacity, np.float32)
        self.capacity = capacity
        self.end = 0

    def append(self, samples):
        n = len(samples)
        indices = np.arange(self.end, self.end + n) % self.capacity
        self.data[indices] = samples
        self.end += n

    def get(self, start, end):
        start = max(0, self.end - self.capacity, start)
        end = min(end, self.end)
        return self.data[np.arange(start, end) % self.capacity].copy()


class Detector:
    """One independent Silero state per source, with bounded pre/post-roll history."""
    def __init__(self, model_path, settings):
        c = sherpa_onnx.VadModelConfig()
        c.silero_vad.model = str(model_path)
        c.silero_vad.threshold = settings['threshold']
        c.silero_vad.min_silence_duration = settings['silence_ms'] / 1000
        c.silero_vad.min_speech_duration = settings['min_speech_ms'] / 1000
        c.silero_vad.max_speech_duration = settings['max_speech_s']
        c.sample_rate = 16000
        c.num_threads = 1
        c.provider = 'cpu'
        self.vad = sherpa_onnx.VoiceActivityDetector(c, buffer_size_in_seconds=60)
        self.window = c.silero_vad.window_size
        self.pending = np.empty(0, np.float32)
        self.ring = SampleRing(40 * 16000)
        self.pre = int(settings['pre_roll_ms'] * 16)
        self.post = int(settings['post_roll_ms'] * 16)
        self.maximum = int(settings['max_speech_s'] * 16000)
        self.active_samples = 0
        self.last_end = 0

    @property
    def speaking(self):
        return self.vad.is_speech_detected()

    def accept(self, samples):
        self.pending = np.concatenate((self.pending, samples))
        results = []
        while len(self.pending) >= self.window:
            frame = self.pending[:self.window]
            self.pending = self.pending[self.window:]
            self.ring.append(frame)
            self.vad.accept_waveform(frame)
            self.active_samples = self.active_samples + self.window if self.speaking else 0
            if self.active_samples >= self.maximum:
                self.vad.flush()
                self.active_samples = 0
            results.extend(self._collect())
        return results

    def _collect(self):
        results = []
        while not self.vad.empty():
            segment = self.vad.front
            speech_start = int(segment.start)
            speech_end = speech_start + len(segment.samples)
            start = max(self.last_end, speech_start - self.pre, 0)
            end = min(self.ring.end, speech_end + self.post)
            if end > start:
                results.append((start, speech_end, self.ring.get(start, end)))
                self.last_end = end
            self.vad.pop()
        return results

    def flush(self):
        results = []
        if len(self.pending):
            results += self.accept(np.zeros(self.window - len(self.pending), np.float32))
        self.vad.flush()
        return results + self._collect()
