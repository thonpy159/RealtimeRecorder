import json
import threading
from PySide6.QtCore import QTimer


def attach_smoke_test(application, window):
    report = {'states': [], 'errors': [], 'cycles': 0, 'capture': []}
    def stopped_capture():
        report['capture'].append([{'speaker': c.speaker.value, 'frames': c.frames, 'rms_peak': c.peak}
                                  for c in window.controller.channels])
        window.stop_button.click()

    def state(value):
        report['states'].append(value)
        if value == '準備完了' and report['cycles'] == 0:
            window.grab().save(str(window.root / 'logs' / 'gui-ready.png'))
            if window.start_button.isEnabled():
                QTimer.singleShot(100, window.start_button.click)
            else:
                report['errors'].append('Audio devices unavailable')
                QTimer.singleShot(100, window.begin_close)
        elif value == '録音中':
            report['cycles'] += 1
            QTimer.singleShot(6000, stopped_capture)
        elif value == '停止中' and not window.closing:
            if report['cycles'] < 2 and not report['errors']:
                QTimer.singleShot(100, window.start_button.click)
            else:
                QTimer.singleShot(100, window.begin_close)
        elif value == 'エラー' and not window.closing:
            QTimer.singleShot(100, window.begin_close)

    def finished():
        report['remaining_threads'] = [t.name for t in threading.enumerate() if t.name != 'MainThread']
        report['passed'] = report['cycles'] == 2 and not report['errors'] and not report['remaining_threads'] and all(
            row['frames'] > 0 for cycle in report['capture'] for row in cycle)
        (window.root / 'logs' / 'gui-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        print(json.dumps(report, ensure_ascii=True), flush=True)
        application.exit(0 if report['passed'] else 1)

    window.controller.state.connect(state)
    window.controller.error.connect(report['errors'].append)
    window.controller.closed.connect(finished)
    QTimer.singleShot(120000, lambda: window.begin_close() if not window.closing else None)
