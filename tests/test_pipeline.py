import copy
from queue import Queue
import threading
import time
import numpy as np
import pytest
from app.pipeline import Channel
from app.records import Speaker
from app.config.settings import DEFAULTS


class FakeSource:
    sample_rate = 16000
    channels = 1
    def __init__(self):
        self.queue = Queue()
        self.closed = False
        self.stopped = False
    def open(self):
        pass
    def start(self):
        self.queue.put(np.ones(8000, np.float32).tobytes())
    def check(self):
        pass
    def stop(self):
        self.stopped = True
    def close(self):
        self.closed = True


class FakeDetector:
    speaking = False
    def __init__(self, *args):
        self.chunks = []
    def accept(self, x):
        self.chunks.append(x)
        return []
    def flush(self):
        x = np.concatenate(self.chunks)
        return [(0, len(x), x)]


class Collector:
    def __init__(self):
        self.items = []
    def submit(self, item):
        self.items.append(item)


def test_channel_stop_flush_and_join(monkeypatch):
    monkeypatch.setattr('app.pipeline.Detector', FakeDetector)
    source, collector, errors = FakeSource(), Collector(), []
    channel = Channel(source, Speaker.ME, DEFAULTS['vad'], None, collector, lambda *args: None, errors.append)
    channel.start()
    assert channel.ready.wait(2)
    channel.request_stop()
    channel.join(2)
    assert not channel.is_alive() and source.closed and source.stopped
    assert not errors and len(collector.items) == 1
    assert len(collector.items[0].audio) == 8000


def test_device_failure_does_not_crash_worker(monkeypatch):
    monkeypatch.setattr('app.pipeline.Detector', FakeDetector)
    class Disconnected(FakeSource):
        def check(self):
            raise OSError('device unplugged')
    source, errors = Disconnected(), []
    channel = Channel(source, Speaker.OTHER, DEFAULTS['vad'], None, Collector(), lambda *args: None, errors.append)
    channel.start()
    channel.join(2)
    assert not channel.is_alive() and source.closed and errors


def test_open_failure_closes_source(monkeypatch):
    class Broken(FakeSource):
        def open(self):
            raise OSError('no microphone')
    source, errors = Broken(), []
    channel = Channel(source, Speaker.ME, DEFAULTS['vad'], None, Collector(), lambda *args: None, errors.append)
    channel.start()
    channel.join(2)
    assert source.closed and channel.start_error and errors


def test_vad_failure_stops_capture(monkeypatch):
    class BrokenDetector(FakeDetector):
        def accept(self, samples):
            raise RuntimeError('VAD error')
    monkeypatch.setattr('app.pipeline.Detector', BrokenDetector)
    source, errors = FakeSource(), []
    channel = Channel(source, Speaker.ME, DEFAULTS['vad'], None, Collector(), lambda *args: None, errors.append)
    channel.start()
    channel.join(2)
    assert not channel.is_alive() and source.closed and errors
