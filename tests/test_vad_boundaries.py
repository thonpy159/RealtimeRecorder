from types import SimpleNamespace
import numpy as np
from app.vad.detector import Detector, SampleRing


def test_vad_pre_and_post_roll_do_not_drop_initial_audio():
    d = Detector.__new__(Detector)
    d.pre, d.post, d.last_end = 3200, 2400, 0
    d.ring = SampleRing(64000)
    d.ring.append(np.arange(32000, dtype=np.float32))
    class Native:
        segments = [SimpleNamespace(start=8000, samples=np.zeros(8000))]
        def empty(self):
            return not self.segments
        @property
        def front(self):
            return self.segments[0]
        def pop(self):
            self.segments.pop(0)
    d.vad = Native()
    start, end, audio = d._collect()[0]
    assert start == 4800 and end == 16000
    np.testing.assert_array_equal(audio, np.arange(4800, 18400))


def test_hard_maximum_flushes_continuous_speech():
    d = Detector.__new__(Detector)
    d.window, d.maximum, d.active_samples = 512, 32000, 0
    d.pre, d.post, d.last_end = 3200, 2400, 0
    d.pending = np.empty(0, np.float32)
    d.ring = SampleRing(40 * 16000)
    class Native:
        def __init__(self):
            self.start, self.end, self.segments = 0, 0, []
        def accept_waveform(self, samples):
            self.end += len(samples)
        def is_speech_detected(self):
            return True
        def flush(self):
            self.segments.append(SimpleNamespace(start=self.start, samples=np.zeros(self.end-self.start)))
            self.start = self.end
        def empty(self):
            return not self.segments
        @property
        def front(self):
            return self.segments[0]
        def pop(self):
            self.segments.pop(0)
    d.vad = Native()
    output = d.accept(np.ones(16000 * 7, np.float32)) + d.flush()
    assert len(output) == 4
    assert all(len(x) <= 32000 + 512 for _, _, x in output)
    assert sum(len(x) for _, _, x in output) >= 16000 * 7
