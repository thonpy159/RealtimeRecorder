import logging
from queue import Queue, Full
import threading
import time
import pyaudiowpatch as pa

log = logging.getLogger(__name__)


class AudioSource:
    """PortAudio callback only copies PCM. VAD/resampling run elsewhere."""
    loopback = False

    def __init__(self, device_index=None):
        self.device_index = device_index
        self.queue = Queue(maxsize=150)  # at most three seconds, then explicit error
        self.error = None
        self.p = None
        self.stream = None
        self.keepalive = None
        self.last_callback = time.monotonic()
        self.closing = threading.Event()

    def open(self):
        self.p = pa.PyAudio()
        try:
            if self.device_index is None:
                d = (self.p.get_default_wasapi_loopback() if self.loopback else self.p.get_default_wasapi_device(d_in=True))
            else:
                d = self.p.get_device_info_by_index(self.device_index)
            if bool(d.get('isLoopbackDevice', False)) != self.loopback:
                raise RuntimeError('選択したデバイスの種類が変わりました。一覧を更新してください。')
            self.device = d
            self.sample_rate = int(d['defaultSampleRate'])
            self.channels = int(d['maxInputChannels']) if self.loopback else min(2, int(d['maxInputChannels']))
            if self.channels < 1:
                raise RuntimeError('音声入力チャンネルがありません')
            log.info('Audio device: %s rate=%d channels=%d', d['name'], self.sample_rate, self.channels)
            self.stream = self.p.open(format=pa.paFloat32, channels=self.channels,
                                      rate=self.sample_rate, input=True, input_device_index=int(d['index']),
                                      frames_per_buffer=max(128, self.sample_rate // 50),
                                      stream_callback=self._callback, start=False)
            if self.loopback:
                # WASAPI delivers no loopback packets when the endpoint is idle.
                # A zero-valued render stream keeps its clock advancing through silence,
                # so VAD sees end-of-speech and timestamps do not lose silent intervals.
                output_name = d['name'].removesuffix(' [Loopback]')
                output = next(self.p.get_device_info_by_index(i) for i in range(self.p.get_device_count())
                              if self.p.get_device_info_by_index(i)['hostApi'] == d['hostApi']
                              and self.p.get_device_info_by_index(i)['maxOutputChannels'] > 0
                              and self.p.get_device_info_by_index(i)['name'] == output_name)
                self.keepalive = self.p.open(format=pa.paFloat32, channels=self.channels,
                    rate=self.sample_rate, output=True, output_device_index=int(output['index']),
                    frames_per_buffer=max(128, self.sample_rate // 50), start=False,
                    stream_callback=lambda data, count, info, status: (bytes(count * self.channels * 4), pa.paContinue))
        except Exception:
            self.close()
            raise

    def _callback(self, data, frame_count, time_info, status):
        self.last_callback = time.monotonic()
        if self.closing.is_set():
            return (None, pa.paComplete)
        if status:
            self.error = RuntimeError(f'音声取得でオーバーフロー等を検出しました (status={status})')
            return (None, pa.paAbort)
        try:
            self.queue.put_nowait(data)
        except Full:
            self.error = RuntimeError('音声処理が追いつきません。CPU負荷を下げて再開してください。')
            return (None, pa.paAbort)
        return (None, pa.paContinue)

    def start(self):
        self.last_callback = time.monotonic()
        if self.keepalive is not None:
            self.keepalive.start_stream()
        self.stream.start_stream()

    def check(self):
        if self.error:
            raise self.error
        if not self.stream.is_active() or time.monotonic() - self.last_callback > 5:
            raise RuntimeError('音声デバイスが停止しました。接続を確認して一覧を更新してください。')

    def stop(self):
        self.closing.set()
        if self.stream is not None:
            self.stream.stop_stream()
        if self.keepalive is not None:
            self.keepalive.stop_stream()

    def close(self):
        for stream in (self.stream, self.keepalive):
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    log.exception('Audio stream close failed')
        self.stream = self.keepalive = None
        if self.p is not None:
            try:
                self.p.terminate()
            except Exception:
                log.exception('PortAudio terminate failed')
            self.p = None
