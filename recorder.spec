# Reproducible lightweight Windows GUI build. Models are copied by build_release.py.
from PyInstaller.utils.hooks import collect_dynamic_libs
from pathlib import Path
import PySide6

a = Analysis(['main.py'], pathex=[SPECPATH],
    binaries=collect_dynamic_libs('sherpa_onnx') + collect_dynamic_libs('sherpa_onnx_core') + collect_dynamic_libs('soxr'),
    datas=[('app/ui/chevron.svg', 'app/ui')],
    hiddenimports=[], hookspath=[], hooksconfig={},
    excludes=['faster_whisper','ctranslate2','av','onnxruntime','huggingface_hub',
              'tokenizers','torch','tensorflow','pytest','pip','setuptools','matplotlib',
              'PySide6.QtWebEngineCore','PySide6.QtQml','PySide6.QtQuick','PySide6.QtPdf'],
    noarchive=False, optimize=1)
# Qt uses Windows' system ICU. An unrelated ICU on the build machine's PATH
# has incompatible exports and must never shadow the Windows DLL.
# This widget application does not use PDF rendering or the QML keyboard.
unused = {'icuuc.dll', 'icudt78.dll', 'qpdf.dll', 'qtvirtualkeyboardplugin.dll',
          'Qt6Pdf.dll', 'Qt6Quick.dll', 'Qt6VirtualKeyboard.dll',
          'Qt6Qml.dll', 'Qt6QmlMeta.dll', 'Qt6QmlModels.dll', 'Qt6QmlWorkerScript.dll'}
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name not in unused]
# Use Qt's newer, backward-compatible MSVC runtime at the application root too.
qt_dir = Path(PySide6.__file__).parent
a.binaries = [(dest, str(qt_dir / dest), kind)
              if dest in ('VCRUNTIME140.dll', 'VCRUNTIME140_1.dll') else (dest, source, kind)
              for dest, source, kind in a.binaries]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='RealtimeRecorder',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='RealtimeRecorder')
