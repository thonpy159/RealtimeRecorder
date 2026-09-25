import argparse
import copy
import logging
import sys
from PySide6.QtWidgets import QApplication
from app.config.settings import ROOT, DEFAULTS, load_settings
from app.utils.logging import configure_logging
from app.ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true', help='実機の開始・停止を2回確認して正常終了')
    parser.add_argument('--verify-package', action='store_true', help='録音せずモデルとGUIを確認して終了')
    args = parser.parse_args()
    configure_logging(ROOT / 'logs')
    application = QApplication(sys.argv)
    application.setStyle('Fusion')
    application.setApplicationName('リアルタイムレコーダー')
    config_error = None
    try:
        settings = load_settings()
    except ValueError as e:
        logging.exception('Invalid configuration')
        settings = copy.deepcopy(DEFAULTS)
        config_error = str(e)
    if getattr(sys, 'frozen', False):
        settings['asr_engine'] = 'reazon'
    window = MainWindow(settings, ROOT)
    if config_error:
        window.show_error(config_error + '。今回は既定値で起動しました。')
        window.threads.setEnabled(False)
        window.engine.setEnabled(False)
    window.show()
    application.commitDataRequest.connect(lambda manager: window.begin_close() if not window.closing else None)
    if args.smoke_test:
        from scripts.gui_smoke import attach_smoke_test
        attach_smoke_test(application, window)
    elif args.verify_package:
        from app.package_check import attach_package_check
        attach_package_check(application, window)
    result = application.exec()
    if window.controller.thread.is_alive():
        window.controller.command('close')
        window.controller.thread.join()
    return result


if __name__ == '__main__':
    sys.exit(main())
