from datetime import datetime
import html
import logging
from pathlib import Path
import time
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QTextBrowser, QVBoxLayout, QWidget)
from app.config.settings import save_settings
from app.controller import Controller
from app.records import markdown, ordered, Speaker
from app.ui.dialogs import confirmation


class MainWindow(QMainWindow):
    def __init__(self, settings, root, controller_factory=Controller):
        super().__init__()
        self.settings, self.root = settings, root
        self.records = []
        self.unsaved = False
        self.closing = False
        self.can_close = False
        self.current_state = '準備中'
        self.testing_mic = False
        self.test_texts = []
        self.meter_peak = 0
        self._test_timer_started = False
        self.test_timer = QTimer(self)
        self.test_timer.setSingleShot(True)
        self.test_timer.timeout.connect(self.stop_capture)
        from app.ui.layout import build_window
        build_window(self, settings, root)
        self.controller = controller_factory(settings, root)
        self.controller.state.connect(self.set_state)
        self.controller.error.connect(self.show_error)
        self.controller.devices.connect(self.set_devices)
        self.controller.result.connect(self.add_result)
        self.controller.meter.connect(self.set_meter)
        self.controller.busy.connect(self.set_busy)
        self.controller.closed.connect(self.finished_close)
        self.controller.exported.connect(self.saved)
        self.start_button.clicked.connect(self.start_capture)
        self.stop_button.clicked.connect(self.stop_capture)
        self.refresh.clicked.connect(self.refresh_devices)
        self.threads.currentTextChanged.connect(self.set_threads)
        self.clear_button.clicked.connect(self.clear)
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(markdown(self.records)))
        self.save_button.clicked.connect(self.save)
        self.set_state('準備中')
        self.controller.command('prepare')

    def set_state(self, state):
        self.current_state = state
        display = {'準備中': '準備しています…', '準備完了': '開始できます',
                   '録音中': '文字起こし中', '停止処理中': '残りの音声を処理中…',
                   '停止中': '停止しました', '終了処理中': '終了しています…'}.get(state, state)
        if state in ('準備完了', '停止中'):
            if not self.mic.count():
                display = 'マイク未接続'
            elif not self.loop.count():
                display = '再生先を確認してください'
        self.status.setText('マイクをテスト中' if self.testing_mic and state == '録音中' else display)
        if self.testing_mic and state == '録音中' and not self._test_timer_started:
            self._test_timer_started = True
            self.test_timer.start(8000)
        if state in ('停止中', 'エラー') and self.testing_mic:
            self.test_timer.stop()
            self.testing_mic = False
            if self.test_texts:
                self.test_result.setText('認識結果\n' + '\n'.join(self.test_texts))
            elif self.meter_peak < 12:
                self.test_result.setText('声がほとんど届いていません。\nマイクの選択・ミュート・口との距離を確認してください。')
            else:
                self.test_result.setText('音は入りましたが、言葉を認識できませんでした。\nマイクの近くで、短い文をもう一度お試しください。')
        idle = state in ('停止中', '準備完了', 'エラー') and not self.closing
        self.start_button.setEnabled(idle and self.mic.count() > 0 and self.loop.count() > 0)
        self.stop_button.setEnabled(state == '録音中' and not self.closing)
        self.refresh.setEnabled(idle)
        self.recheck_devices.setEnabled(idle)
        self.recheck_devices.setText('確認中…' if state == '準備中' else '接続を再確認')
        self.mic.setEnabled(idle)
        self.loop.setEnabled(idle)
        self.test_button.setEnabled(idle and self.mic.count() > 0)
        if state == '録音中':
            self.asr_status.setText('話し終わると認識します。小さい声は自動で補正します。')
        elif state in ('準備完了', '停止中'):
            self.asr_status.setText('音声は外部送信・保存しません。文字は保存ボタンで保存できます。')

    def set_busy(self, busy):
        if busy:
            self.asr_status.setText('音声を日本語に変換しています…')
        elif self.current_state == '録音中':
            self.asr_status.setText('次の発話を待っています')

    def test_microphone(self):
        self.testing_mic = True
        self.test_texts = []
        self.meter_peak = 0
        self._test_timer_started = False
        self.test_result.setText('8秒間、マイクだけを確認します。\n「あいうえお」や「今日はよろしくお願いします」と話してください。')
        self.test_result.show()
        self.error_label.hide()
        self.set_state('準備中')
        self.controller.command('test_mic', (self.mic.currentData(),))

    def set_devices(self, devices):
        missing = []
        for combo, key, label in ((self.mic, 'microphones', 'Windowsの既定マイク'),
                                  (self.loop, 'loopbacks', 'Windowsの既定再生デバイス')):
            previous = combo.currentText()
            combo.clear()
            if devices[key]:
                combo.addItem(label, None)
                for d in devices[key]:
                    combo.addItem(d['name'].replace(' [Loopback]', ''), int(d['index']))
                i = combo.findText(previous)
                if i >= 0:
                    combo.setCurrentIndex(i)
            else:
                missing.append('マイク' if key == 'microphones' else '再生デバイス（スピーカー・ヘッドホン）')
        self.device_notice.setVisible(bool(missing))
        if missing:
            self.device_message.setText('・'.join(missing) + 'が見つかりません。\n機器を接続して「接続を再確認」を押してください。')
        self.set_state(self.current_state)

    def set_threads(self, value):
        self.settings['asr_threads'] = int(value)
        try:
            save_settings(self.settings, self.root / 'config.json')
            self.thread_hint.setText('保存しました。次回起動時に適用')
        except OSError:
            logging.exception('Config write failed')
            self.show_error('CPU設定を保存できませんでした。フォルダの書き込み権限を確認してください。')

    def set_engine(self):
        self.settings['asr_engine'] = self.engine.currentData()
        try:
            save_settings(self.settings, self.root / 'config.json')
            self.thread_hint.setText('保存しました。アプリを再起動すると反映されます。')
        except OSError:
            logging.exception('Engine setting save failed')
            self.show_error('認識エンジンの設定を保存できませんでした。')

    def start_capture(self):
        self.error_label.hide()
        self.set_state('準備中')
        self.controller.command('start', (self.mic.currentData(), self.loop.currentData()))

    def stop_capture(self):
        self.set_state('停止処理中')
        self.controller.command('stop')

    def refresh_devices(self):
        self.error_label.hide()
        self.set_state('準備中')
        self.controller.command('refresh')

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()

    def set_meter(self, speaker, level, speaking):
        self.levels[speaker].setValue(level)
        text = '発話中 — 声が届いています' if speaking else ('音声を検出しています' if level >= 25 else '入力待ち — 話して音量を確認')
        self.speech_labels[speaker].setText(text)
        if self.testing_mic and speaker == 'ME':
            self.meter_peak = max(self.meter_peak, level)

    def add_result(self, record):
        record.total_latency_ms = max(0, (time.monotonic() - record.ended_monotonic) * 1000)
        logging.info('GUI id=%s total_latency_ms=%.1f', record.id, record.total_latency_ms)
        if self.testing_mic:
            self.test_texts.append(record.display_text)
            self.test_result.setText('認識結果\n' + '\n'.join(self.test_texts))
            return
        self.records.append(record)
        self.records = ordered(self.records)
        self.unsaved = True
        self.render_records()

    def render_records(self):
        bar = self.transcript.verticalScrollBar()
        old = bar.value()
        at_bottom = self.settings['ui']['auto_scroll'] and bar.maximum() - old < 30
        blocks = []
        for r in self.records:
            color = '#edf4ff' if r.speaker == Speaker.ME else '#eef7f2'
            label_color = '#215da7' if r.speaker == Speaker.ME else '#246e51'
            blocks.append(f'<table width="100%" bgcolor="{color}" cellpadding="14"><tr><td>'
                          f'<span style="color:{label_color}; font-size:13px"><b>{r.speaker.label}</b>　{r.speech_started_at:%H:%M:%S}</span><br>'
                          f'<span style="color:#14243a; font-size:{self.settings["ui"]["font_size"] + 4}px">'
                          f'{html.escape(r.display_text).replace(chr(10), "<br>")}</span></td></tr></table><br>')
        self.transcript.setHtml('<html><body>' + ''.join(blocks) + '</body></html>')
        bar.setValue(bar.maximum() if at_bottom else old)
        self.count_label.setText(f'{len(self.records)} 発話')

    def clear(self):
        if self.records and not confirmation(self, '履歴を消去', '表示中の文字起こしを消去しますか？未保存の内容は失われます。', '履歴を消去'):
            return
        self.records.clear()
        self.unsaved = False
        self.render_records()

    def save(self):
        name, _ = QFileDialog.getSaveFileName(self, 'Markdown保存',
            str(self.root / f'文字起こし_{datetime.now():%Y%m%d_%H%M%S}.md'), 'Markdown (*.md)')
        if name:
            self.controller.command('export', (Path(name), markdown(self.records), len(self.records)))

    def saved(self, count):
        self.unsaved = len(self.records) != count
        self.count_label.setText(f'{count} 発話・保存しました')

    def closeEvent(self, event):
        if self.can_close:
            event.accept()
            return
        event.ignore()
        if self.closing:
            return
        if self.unsaved and not confirmation(self, '終了', '未保存の文字起こしがあります。保存せず終了しますか？', '保存せず終了'):
            return
        self.begin_close()

    def begin_close(self):
        self.test_timer.stop()
        self.closing = True
        self.set_state('終了処理中')
        self.controller.command('close')

    def finished_close(self):
        self.controller.thread.join()
        self.can_close = True
        self.close()
