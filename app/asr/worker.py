import logging
from queue import Queue
import threading
import time
import numpy as np
from app.records import replace_terms, format_japanese

log = logging.getLogger(__name__)


class ASRWorker(threading.Thread):
    def __init__(self, recognizer, dictionary, on_result, on_error, on_busy=lambda value: None, queue_size=32):
        super().__init__(name='ASR', daemon=False)
        self.recognizer = recognizer
        self.dictionary = dictionary
        self.on_result = on_result
        self.on_error = on_error
        self.on_busy = on_busy
        self.queue = Queue(queue_size)

    def submit(self, utterance):
        self.queue.put_nowait(utterance)

    def run(self):
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                if len(item.audio) < 1600:
                    continue
                self.on_busy(True)
                started = time.perf_counter()
                item.audio_duration_ms = len(item.audio) / 16
                try:
                    item.raw_text = self.recognizer.recognize(item.audio)
                finally:
                    item.audio = np.empty(0, dtype=np.float32)
                item.asr_processing_ms = (time.perf_counter() - started) * 1000
                item.total_latency_ms = max(0, (time.monotonic() - item.ended_monotonic) * 1000)
                item.display_text = format_japanese(replace_terms(item.raw_text, self.dictionary))
                log.info('ASR id=%s speaker=%s audio_duration_ms=%.1f asr_processing_ms=%.1f RTF=%.3f total_latency_ms=%.1f',
                         item.id, item.speaker.value, item.audio_duration_ms, item.asr_processing_ms,
                         item.asr_processing_ms / item.audio_duration_ms, item.total_latency_ms)
                if item.display_text:
                    self.on_result(item)
            except Exception:
                log.exception('ASR failed')
                self.on_error('音声認識に失敗しました。次の発話から処理を続けます。詳細はログを確認してください。')
            finally:
                if item is not None:
                    item.audio = np.empty(0, dtype=np.float32)
                self.on_busy(False)
                self.queue.task_done()

    def drain(self):
        self.queue.join()

    def shutdown(self):
        self.queue.put(None)
        self.join()
