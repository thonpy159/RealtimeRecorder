from datetime import datetime, timedelta
import logging
from queue import Empty, Full
import threading
import time
import numpy as np
from app.audio.preprocess import AudioPreprocessor
from app.records import Utterance, Speaker
from app.vad.detector import Detector

log = logging.getLogger(__name__)


class Channel(threading.Thread):
    def __init__(self, source, speaker, settings, model_path, asr, meter, failed):
        super().__init__(name=f'Audio-VAD-{speaker.value}', daemon=False)
        self.source, self.speaker = source, speaker
        self.settings, self.model_path = settings, model_path
        self.asr, self.meter, self.failed = asr, meter, failed
        self.stopping = threading.Event()
        self.ready = threading.Event()
        self.start_error = None
        self.frames = 0
        self.peak = 0.0
        self.raw_peak = 0.0
        self.raw_rms_peak = 0.0

    def request_stop(self):
        self.stopping.set()

    def _submit(self, segments):
        for start, end, audio in segments:
            if len(audio) < self.settings['min_speech_ms'] * 16:
                continue
            item = Utterance(self.speaker, self.origin + timedelta(seconds=start / 16000),
                             self.origin + timedelta(seconds=end / 16000), audio,
                             self.origin_monotonic + end / 16000)
            try:
                self.asr.submit(item)
            except Full:
                # Preserve this utterance while stopping capture to bound memory growth.
                self.failed('認識待ちが上限に達しました。音声取得を停止し、残りを処理します。')
                self.asr.queue.put(item)
                self.stopping.set()

    def run(self):
        detector = None
        pre = None
        try:
            self.source.open()
            pre = AudioPreprocessor(self.source.sample_rate, self.source.channels, microphone=self.speaker == Speaker.ME)
            detector = Detector(self.model_path, self.settings)
            self.origin = datetime.now().astimezone()
            self.origin_monotonic = time.monotonic()
            self.source.start()
            self.ready.set()
            last_meter = 0
            while not self.stopping.is_set():
                try:
                    pcm = self.source.queue.get(timeout=0.1)
                except Empty:
                    self.source.check()
                    continue
                self.frames += 1
                x = pre.process(pcm)
                self.raw_peak = max(self.raw_peak, pre.raw_peak)
                self.raw_rms_peak = max(self.raw_rms_peak, pre.raw_rms)
                level = float(np.sqrt(np.mean(x * x))) if len(x) else 0
                self.peak = max(self.peak, level)
                self._submit(detector.accept(x))
                if time.monotonic() - last_meter > 0.1:
                    self.meter(self.speaker.value, min(100, int((20 * np.log10(max(level, 1e-5)) + 60) * 100 / 60)), detector.speaking)
                    last_meter = time.monotonic()
                self.source.check()
        except Exception:
            log.exception('Capture/VAD failed (%s)', self.speaker.value)
            message = f'{self.speaker.label}の音声取得を停止しました。接続・Windowsのマイク許可・デバイス選択を確認してください。詳細は logs/app.log にあります。'
            if not self.ready.is_set():
                self.start_error = message
            self.failed(message)
        finally:
            self.ready.set()
            try:
                self.source.stop()
                if pre is not None and detector is not None:
                    while True:
                        try:
                            pcm = self.source.queue.get_nowait()
                        except Empty:
                            break
                        self._submit(detector.accept(pre.process(pcm)))
                    self._submit(detector.accept(pre.process(b'', final=True)))
                    self._submit(detector.flush())
            except Exception:
                log.exception('Audio drain failed')
                self.failed(f'{self.speaker.label}の停止時に残りの音声を処理できませんでした。ログを確認してください。')
            finally:
                log.info('Capture quality speaker=%s blocks=%d raw_rms_peak=%.6f raw_peak=%.6f normalized_rms_peak=%.6f',
                         self.speaker.value, self.frames, self.raw_rms_peak, self.raw_peak, self.peak)
                self.source.close()
                self.meter(self.speaker.value, 0, False)
