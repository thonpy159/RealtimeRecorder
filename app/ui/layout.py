"""Explicit light palette and clear recording controls, independent of Windows theme."""
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget, QScrollArea, QLayout, QSizePolicy)
from app.records import Speaker


def build_window(w, settings, root):
    w.setWindowTitle('リアルタイムレコーダー')
    w.setFixedSize(1120, 740)
    center = QWidget()
    center.setObjectName('page')
    w.setCentralWidget(center)
    page = QVBoxLayout(center)
    page.setContentsMargins(24, 20, 24, 18)
    page.setSpacing(16)
    header = QHBoxLayout()
    titles = QVBoxLayout()
    title = QLabel('リアルタイムレコーダー')
    title.setObjectName('title')
    titles.addWidget(title)
    sub = QLabel('日本語の会話を、このPCだけで文字にします')
    sub.setObjectName('muted')
    titles.addWidget(sub)
    header.addLayout(titles)
    header.addStretch()
    w.status = QLabel('モデルを準備中')
    w.status.setObjectName('statusPill')
    header.addWidget(w.status)
    page.addLayout(header)
    body = QHBoxLayout()
    body.setSpacing(20)
    sidebar = QFrame()
    sidebar.setObjectName('card')
    w.sidebar_scroll = QScrollArea()
    w.sidebar_scroll.setObjectName('inputScroll')
    w.sidebar_scroll.setFixedWidth(294)
    w.sidebar_scroll.setFrameShape(QFrame.NoFrame)
    w.sidebar_scroll.setWidgetResizable(True)
    w.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    w.sidebar_scroll.setWidget(sidebar)
    sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    side = QVBoxLayout(sidebar)
    side.setSizeConstraint(QLayout.SetMinimumSize)
    side.setContentsMargins(16, 18, 16, 18)
    side.setSpacing(12)
    heading = QLabel('音声の入力')
    heading.setObjectName('sectionTitle')
    side.addWidget(heading)
    w.mic, w.loop = QComboBox(), QComboBox()
    w.levels, w.speech_labels, w.level_hints = {}, {}, {}
    for speaker, label, combo in ((Speaker.ME, '自分のマイク', w.mic),
                                  (Speaker.OTHER, '相手の音声（再生先）', w.loop)):
        text = QLabel(label)
        text.setObjectName('fieldLabel')
        side.addWidget(text)
        combo.setMinimumHeight(40)
        combo.setMinimumContentsLength(12)
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.currentTextChanged.connect(lambda text, c=combo: c.setToolTip(text))
        side.addWidget(combo)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        side.addWidget(bar)
        hint = QLabel('開始すると音量を確認できます')
        hint.setObjectName('meterHint')
        hint.setWordWrap(True)
        side.addWidget(hint)
        w.levels[speaker.value] = bar
        w.speech_labels[speaker.value] = hint
        w.level_hints[speaker.value] = hint
    w.test_button = QPushButton('マイクをテストする（8秒）')
    w.test_button.setMinimumHeight(42)
    w.test_button.clicked.connect(w.test_microphone)
    side.addWidget(w.test_button)
    w.refresh = QPushButton('接続した機器を再読み込み')
    w.refresh.setObjectName('subtleButton')
    side.addWidget(w.refresh)
    w.test_result = QLabel('テストでは「あいうえお」や\n「今日はよろしくお願いします」と話してください。')
    w.test_result.setObjectName('testResult')
    w.test_result.setWordWrap(True)
    w.test_result.setTextFormat(Qt.PlainText)
    w.test_result.hide()
    side.addWidget(w.test_result)
    side.addStretch()
    note = QLabel('ヘッドホンを使用してください。\nMeetと同じマイク・再生先を選びます。')
    note.setObjectName('muted')
    note.setWordWrap(True)
    side.addWidget(note)
    w.settings_button = QPushButton('詳細設定 ▾')
    w.settings_button.setObjectName('subtleButton')
    side.addWidget(w.settings_button)
    w.advanced = QWidget()
    advanced = QVBoxLayout(w.advanced)
    advanced.setContentsMargins(0, 0, 0, 0)
    advanced.addWidget(QLabel('認識エンジン（次回起動時）'))
    w.engine = QComboBox()
    w.engine.addItem('ReazonSpeech / 日本語（推奨）', 'reazon')
    if not getattr(sys, 'frozen', False):
        w.engine.addItem('SenseVoice / 比較用', 'sensevoice')
        w.engine.addItem('Whisper small / 比較用', 'small')
        w.engine.addItem('Kotoba / 大型・処理が遅い', 'kotoba')
    w.engine.setCurrentIndex(max(0, w.engine.findData(settings.get('asr_engine', 'reazon'))))
    w.engine.currentIndexChanged.connect(w.set_engine)
    advanced.addWidget(w.engine)
    cpu_row = QHBoxLayout()
    cpu_row.addWidget(QLabel('CPUスレッド数'))
    w.threads = QComboBox()
    w.threads.addItems(['1', '2', '4'])
    w.threads.setCurrentText(str(settings['asr_threads']))
    w.threads.setMinimumWidth(76)
    cpu_row.addWidget(w.threads)
    advanced.addLayout(cpu_row)
    w.thread_hint = QLabel('設定は次回起動時に適用します')
    w.thread_hint.setWordWrap(True)
    w.thread_hint.setObjectName('muted')
    advanced.addWidget(w.thread_hint)
    w.advanced.hide()
    side.addWidget(w.advanced)
    def toggle_settings():
        expanded = not w.advanced.isVisible()
        w.advanced.setVisible(expanded)
        w.settings_button.setText('詳細設定 ▴' if expanded else '詳細設定 ▾')
    w.settings_button.clicked.connect(toggle_settings)
    for label in sidebar.findChildren(QLabel):
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    body.addWidget(w.sidebar_scroll)
    main = QVBoxLayout()
    main.setSpacing(12)
    toolbar = QHBoxLayout()
    heading = QLabel('文字起こし')
    heading.setObjectName('sectionTitle')
    toolbar.addWidget(heading)
    toolbar.addStretch()
    w.count_label = QLabel('0 発話')
    w.count_label.setObjectName('muted')
    toolbar.addWidget(w.count_label)
    main.addLayout(toolbar)
    w.device_notice = QFrame()
    w.device_notice.setObjectName('deviceNotice')
    device_row = QHBoxLayout(w.device_notice)
    device_row.setContentsMargins(12, 12, 12, 12)
    device_row.setSpacing(12)
    w.device_message = QLabel()
    w.device_message.setWordWrap(True)
    w.device_message.setTextFormat(Qt.PlainText)
    device_row.addWidget(w.device_message, 1)
    w.recheck_devices = QPushButton('接続を再確認')
    w.recheck_devices.setMinimumHeight(40)
    w.recheck_devices.clicked.connect(w.refresh_devices)
    device_row.addWidget(w.recheck_devices)
    w.device_notice.hide()
    main.addWidget(w.device_notice)
    w.error_label = QLabel()
    w.error_label.setWordWrap(True)
    w.error_label.setTextFormat(Qt.PlainText)
    w.error_label.setObjectName('errorBox')
    w.error_label.hide()
    main.addWidget(w.error_label)
    w.transcript = QTextBrowser()
    w.transcript.setOpenExternalLinks(False)
    w.transcript.setObjectName('transcript')
    w.transcript.setPlaceholderText('まだ文字起こしはありません\n\n1. 左側でマイクと相手の再生先を確認\n2. 下の「文字起こしを開始」を押す\n3. 話し終えると、ここに文章が表示されます')
    main.addWidget(w.transcript, 1)
    w.asr_status = QLabel('開始前に「マイクをテストする」で認識を確認できます')
    w.asr_status.setObjectName('muted')
    w.asr_status.setWordWrap(True)
    main.addWidget(w.asr_status)
    actions = QHBoxLayout()
    actions.setSpacing(12)
    w.start_button = QPushButton('文字起こしを開始')
    w.start_button.setObjectName('primaryButton')
    w.start_button.setMinimumHeight(52)
    w.stop_button = QPushButton('停止する')
    w.stop_button.setObjectName('stopButton')
    w.stop_button.setMinimumHeight(52)
    actions.addWidget(w.start_button, 2)
    actions.addWidget(w.stop_button, 1)
    main.addLayout(actions)
    body.addLayout(main, 1)
    page.addLayout(body, 1)
    footer = QHBoxLayout()
    w.clear_button = QPushButton('履歴を消去…')
    w.clear_button.setObjectName('subtleButton')
    footer.addWidget(w.clear_button)
    footer.addStretch()
    w.copy_button = QPushButton('全文をコピー')
    w.save_button = QPushButton('文字起こしを保存…')
    for button in (w.copy_button, w.save_button):
        button.setMinimumHeight(40)
        footer.addWidget(button)
    page.addLayout(footer)
    w.setStyleSheet('''
        QWidget { color: #18283c; font-family: "Yu Gothic UI"; font-size: 14px; }
        QWidget#page { background: #eef2f7; }
        QFrame#card { background: white; border: 1px solid #d8e0eb; border-radius: 12px; }
        QScrollArea#inputScroll, QScrollArea#inputScroll > QWidget { background: #ffffff; }
        QLabel { background: transparent; }
        QLabel#title { font-size: 25px; font-weight: 700; color: #10243e; }
        QLabel#sectionTitle { font-size: 19px; font-weight: 700; }
        QLabel#fieldLabel { font-size: 15px; font-weight: 600; }
        QLabel#muted, QLabel#meterHint { color: #52647b; font-size: 13px; }
        QLabel#statusPill { background: #dae8f9; color: #1c4678; padding: 9px 16px; border-radius: 16px; font-weight: 600; }
        QLabel#errorBox { color: #8b211b; background: #fff0ed; border: 1px solid #ebbbb4; padding: 12px; border-radius: 8px; }
        QFrame#deviceNotice { background: #fff0ed; border: 1px solid #ebbbb4; border-radius: 8px; }
        QFrame#deviceNotice QLabel { color: #8b211b; background: transparent; }
        QLabel#testResult { background: #eef5ff; color: #14355e; padding: 10px; border-radius: 6px; }
        QComboBox { color: #18283c; background: #fff; border: 1px solid #a9b8ca; border-radius: 6px; padding: 6px 8px; padding-right: 24px; }
        QComboBox::drop-down { width: 24px; border: none; }
        QComboBox::down-arrow { image: url(ARROW_URL); width: 12px; height: 8px; }
        QComboBox QAbstractItemView { background: #fff; color: #18283c; selection-background-color: #d8e8ff; selection-color: #123d71; padding: 6px; }
        QPushButton { background: #fff; color: #173854; border: 1px solid #a8b9ce; border-radius: 7px; padding: 8px 12px; font-size: 14px; font-weight: 600; }
        QPushButton:hover { background: #e7effb; border-color: #668dbd; }
        QPushButton:pressed { background: #d6e5f8; }
        QPushButton:disabled { color: #77869a; background: #e8edf3; border-color: #d1dae5; }
        QPushButton#primaryButton { color: white; background: #1759b2; border-color: #1759b2; font-size: 17px; }
        QPushButton#primaryButton:hover { background: #104890; }
        QPushButton#primaryButton:disabled { background: #dce5f0; color: #75859a; border-color: #d1dae5; }
        QPushButton#stopButton { color: #a72825; border-color: #cc7670; font-size: 17px; }
        QPushButton#stopButton:enabled { background: #b6322c; color: white; }
        QPushButton#stopButton:disabled { color: #77869a; background: #e8edf3; border-color: #d1dae5; }
        QPushButton#subtleButton { background: transparent; border: none; color: #52647b; font-weight: 400; font-size: 13px; }
        QPushButton#subtleButton:hover { background: #dfe8f4; }
        QTextBrowser#transcript { background: #fff; color: #14243a; border: 1px solid #cbd7e6; border-radius: 10px; padding: 16px; font-size: 18px; selection-background-color: #c8defa; selection-color: #10243e; }
        QProgressBar { background: #e2e9f2; border: none; border-radius: 5px; }
        QProgressBar::chunk { background: #268170; border-radius: 5px; }
        QScrollBar:vertical { width: 12px; background: #edf1f6; }
        QScrollBar::handle:vertical { background: #afbed0; border-radius: 5px; min-height: 28px; }
    '''.replace('ARROW_URL', Path(__file__).with_name('chevron.svg').as_posix()))
