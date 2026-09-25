"""Application-owned confirmations with an explicit, theme-independent palette."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QMessageBox


def confirmation(parent, title, text, action):
    box = QMessageBox(parent)
    box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    box.setWindowTitle(title)
    box.setTextFormat(Qt.PlainText)
    box.setText(text)
    box.setIcon(QMessageBox.Question)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.button(QMessageBox.Yes).setText(action)
    box.button(QMessageBox.No).setText('キャンセル')
    box.setDefaultButton(QMessageBox.No)
    box.setEscapeButton(QMessageBox.No)
    palette = QPalette(box.palette())
    for role, color in ((QPalette.Window, '#ffffff'), (QPalette.WindowText, '#18283c'),
                        (QPalette.Base, '#ffffff'), (QPalette.Text, '#18283c'),
                        (QPalette.Button, '#ffffff'), (QPalette.ButtonText, '#173854')):
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            palette.setColor(group, role, QColor(color))
    box.setPalette(palette)
    box.setStyleSheet('''
        QMessageBox { background-color: #ffffff; color: #18283c; }
        QMessageBox QLabel { background-color: #ffffff; color: #18283c; font-size: 14px; }
        QMessageBox QPushButton { background-color: #ffffff; color: #173854;
            border: 1px solid #a8b9ce; border-radius: 6px; padding: 8px 16px; min-height: 24px; }
        QMessageBox QPushButton:hover { background-color: #e7effb; }
        QMessageBox QPushButton:focus { border: 2px solid #1759b2; }
        QMessageBox QPushButton:pressed { background-color: #d6e5f8; }
    ''')
    try:
        return box.exec() == QMessageBox.Yes
    finally:
        box.deleteLater()
