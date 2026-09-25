"""Verify the final GUI/model startup without opening audio capture streams."""
import json
from pathlib import Path
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.config.settings import ROOT,load_settings
from app.ui.main_window import MainWindow


def main():
    app=QApplication([]); app.setStyle('Fusion')
    window=MainWindow(load_settings(),ROOT)
    report={'ready':False,'audio_capture_started':False,'errors':[]}
    def state(value):
        if value=='準備完了' and not report['ready']:
            report.update(ready=True,engine=window.controller.worker.recognizer.engine,
                          microphone_choices=window.mic.count(),loopback_choices=window.loop.count())
            window.grab().save(str(ROOT/'logs/final-ready.png'))
            QTimer.singleShot(100,window.begin_close)
    def closed():
        report['remaining_threads']=[t.name for t in threading.enumerate() if t.name!='MainThread']
        report['passed']=report['ready'] and report.get('engine')=='reazon' and not report['errors'] and not report['remaining_threads']
        (ROOT/'logs/final-ready.json').write_text(json.dumps(report,indent=2),'utf-8')
        print(json.dumps(report),flush=True)
        app.exit(0 if report['passed'] else 1)
    window.controller.state.connect(state)
    window.controller.error.connect(report['errors'].append)
    window.controller.closed.connect(closed)
    QTimer.singleShot(20000,lambda:window.begin_close() if not window.closing else None)
    window.show()
    sys.exit(app.exec())


if __name__=='__main__': main()
