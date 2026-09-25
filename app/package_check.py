"""Packaged executable diagnostic: bundled public audio, no live recording."""
from datetime import datetime
import json
import threading
import time
import wave
import numpy as np
from PySide6.QtCore import QTimer
from app.records import Utterance, Speaker
from download_models import MODEL_NAME


def attach_package_check(app, window):
    report = {'errors': [], 'recognized': False, 'capture_started': False}
    def ready(state):
        if state != '準備完了' or report.get('submitted'):
            return
        report['submitted'] = True
        report['engine'] = window.controller.worker.recognizer.engine
        try:
            path = window.root / 'models' / MODEL_NAME / 'test_wavs' / '1.wav'
            with wave.open(str(path), 'rb') as source:
                assert source.getframerate() == 16000 and source.getnchannels() == 1 and source.getsampwidth() == 2
                x = np.frombuffer(source.readframes(source.getnframes()), '<i2').astype(np.float32) / 32768
            now = datetime.now().astimezone()
            window.controller.worker.submit(Utterance(Speaker.ME, now, now, x, time.monotonic()))
        except Exception as error:
            report['errors'].append(str(error))
            window.begin_close()
    def result(record):
        report['recognized'] = bool(record.raw_text)
        report['text'] = record.raw_text
        report['asr_ms'] = record.asr_processing_ms
        window.grab().save(str(window.root / 'logs' / 'package-check.png'))
        QTimer.singleShot(50, window.begin_close)
    def closed():
        report['remaining_threads'] = [t.name for t in threading.enumerate() if t.name != 'MainThread']
        report['passed'] = report['recognized'] and not report['errors'] and not report['remaining_threads']
        (window.root / 'logs' / 'package-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        app.exit(0 if report['passed'] else 1)
    window.controller.state.connect(ready)
    window.controller.result.connect(result)
    window.controller.error.connect(report['errors'].append)
    window.controller.closed.connect(closed)
    QTimer.singleShot(60000, lambda: window.begin_close() if not window.closing else None)
