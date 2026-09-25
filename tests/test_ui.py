import copy
from datetime import datetime, timedelta, timezone
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from app.config.settings import DEFAULTS
from app.records import Utterance, Speaker
from app.ui.main_window import MainWindow


class FakeController(QObject):
    state = Signal(str)
    error = Signal(str)
    devices = Signal(object)
    result = Signal(object)
    meter = Signal(str, int, bool)
    busy = Signal(bool)
    closed = Signal()
    exported = Signal(int)
    def __init__(self, *args):
        super().__init__()
        self.commands = []
    def command(self, *args):
        self.commands.append(args)


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = MainWindow(copy.deepcopy(DEFAULTS), tmp_path, FakeController)
    w.show()
    app.processEvents()
    yield w
    w.can_close = True
    w.close()
    app.processEvents()


def record(i):
    t = datetime(2026, 9, 17, tzinfo=timezone.utc) + timedelta(seconds=i)
    return Utterance(Speaker.ME if i % 2 else Speaker.OTHER, t, t, np.empty(0, np.float32),
                     display_text=f'テスト発話 {i} <script>安全な表示</script>')


def test_gui_sort_and_escape(window):
    window.add_result(record(2))
    window.add_result(record(1))
    text = window.transcript.toPlainText()
    assert text.index('テスト発話 1') < text.index('テスト発話 2')
    assert '<script>' in text and '自分' in text and '相手' in text


def test_scroll_position_preserved(window):
    for i in range(25):
        window.add_result(record(i))
    QApplication.processEvents()
    bar = window.transcript.verticalScrollBar()
    assert bar.maximum() > 100
    assert bar.value() == bar.maximum()
    bar.setValue(20)
    window.add_result(record(30))
    assert bar.value() == 20
    bar.setValue(bar.maximum())
    window.add_result(record(31))
    assert bar.value() == bar.maximum()


def test_start_stop_state_and_no_devices(window):
    window.set_state('準備完了')
    assert not window.start_button.isEnabled()
    window.set_devices({'microphones': [{'name': 'Mic', 'index': 1}], 'loopbacks': [{'name': 'Loop', 'index': 2}]})
    assert window.start_button.isEnabled()
    window.start_button.click()
    assert window.controller.commands[-1] == ('start', (None, None))
    assert not window.start_button.isEnabled()
    window.set_state('録音中')
    window.stop_button.click()
    assert window.controller.commands[-1] == ('stop',)


def test_save_snapshot_does_not_mark_new_result_saved(window):
    window.add_result(record(1))
    window.add_result(record(2))
    window.saved(1)
    assert window.unsaved


def test_meter_and_error(window):
    window.set_meter('OTHER', 78, True)
    assert window.levels['OTHER'].value() == 78
    assert '発話中' in window.speech_labels['OTHER'].text()
    window.show_error('失敗しました')
    assert window.error_label.isVisible()


def test_microphone_test_only_starts_microphone_and_keeps_results_separate(window):
    window.set_devices({'microphones': [{'name': 'Mic', 'index': 1}], 'loopbacks': []})
    window.set_state('準備完了')
    assert window.test_button.isEnabled() and not window.start_button.isEnabled()
    window.test_button.click()
    assert window.controller.commands[-1] == ('test_mic', (None,))
    window.set_state('録音中')
    assert window.test_timer.isActive()
    r = record(1)
    r.display_text = '今日はよろしくお願いします。'
    window.add_result(r)
    assert not window.records and r.display_text in window.test_result.text()
    window.set_state('停止中')
    assert not window.test_timer.isActive() and not window.testing_mic


def test_microphone_test_reports_missing_signal(window):
    window.test_microphone()
    window.set_state('録音中')
    window.set_meter('ME', 0, False)
    window.set_state('停止中')
    assert '声がほとんど届いていません' in window.test_result.text()
