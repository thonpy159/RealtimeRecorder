import copy
from pathlib import Path
import threading
from PySide6.QtWidgets import QApplication
from app.config.settings import DEFAULTS
from app.controller import Controller


def test_controller_model_loaded_once_stop_restart_and_export(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    loaded = []
    class Model:
        def __init__(self, *args, **kwargs):
            loaded.append(self)
        def recognize(self, audio):
            return 'test'
    class Channel:
        start_error = None
        def __init__(self, *args):
            self.ready = threading.Event()
        def start(self):
            self.ready.set()
        def request_stop(self):
            pass
        def join(self):
            pass
    monkeypatch.setattr('app.controller.Recognizer', Model)
    monkeypatch.setattr('app.controller.Channel', Channel)
    monkeypatch.setattr('app.controller.enumerate_devices', lambda: {})
    c = Controller(copy.deepcopy(DEFAULTS), tmp_path)
    errors, saves = [], []
    c.error.connect(errors.append)
    c.exported.connect(saves.append)
    try:
        c.command('prepare')
        c.command('start', (None, None))
        c.command('stop')
        c.command('start', (None, None))
        c.command('stop')
        c.commands.join()
        assert len(loaded) == 1 and c.worker.is_alive() and not c.channels
        target = tmp_path / 'transcript.md'
        c.command('export', (target, '# テスト\n', 1))
        c.command('export', (tmp_path / 'missing' / 'fail.md', 'test', 2))
        c.commands.join()
        app.processEvents()
        assert target.read_text('utf-8') == '# テスト\n'
        assert saves == [1] and len(errors) == 1
    finally:
        c.command('close')
        c.thread.join(3)
    assert not c.thread.is_alive() and c.worker is None
