# Windows 配布版の作成

プロジェクト直下から、このプロジェクト専用の Python で実行します。

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3 pyinstaller-hooks-contrib==2026.7
.venv\Scripts\python.exe scripts\build_release.py --zip
```

出力は `dist/RealtimeRecorder-Windows-x64.zip` です。ZIPをすべて展開し、
`RealtimeRecorder.exe` を起動します。利用者側にPythonは不要です。
exe単体ではなく `_internal`、`models`、ライセンスを含むフォルダ一式を配布します。
開発用のBATは配布には使いません。Windows GUI形式なのでコンソールは開きません。

現在使用中のReazonSpeech INT8とSilero VADだけを同梱します。モデルの再量子化や
認識設定の精度低下は行いません。比較用モデル、開発用ライブラリ、個人の設定、
ログ、文字起こしはZIPに含めません。config.jsonはアプリの既定値から生成して同梱します。ローカルの個人設定はコピーしません。ログは展開先に作成するポータブル形式です。
書き込みできる場所へ展開してください。

単一exe形式では起動ごとに内部ファイルを一時展開するため、フォルダ形式を採用しています。
モデル自体の容量は必要です。ZIP圧縮は可逆で、展開後の認識精度には影響しません。

動作確認は展開したexeに `--verify-package` を付けて実行します。
公開サンプル音声を実際の認識ワーカーに渡し、GUI表示と終了を確認します。
`logs/package-check.json` の `passed: true`、終了コード0を確認してください。
実マイクを録音する検査ではありません。別PCへの公開前には対象Windowsでも確認してください。

`recorder.spec` はWindows標準ICUを利用します。ビルド端末のPATHにある他ソフトの
同名ICU DLLを同梱すると起動できないため除外しています。Qtに同梱されたMSVCランタイムを
利用し、未使用のPDF・QMLキーボードも除外します。

再ビルドは `dist/RealtimeRecorder` を置き換えます。そのフォルダを日常利用している場合は
先に別の場所へ移し、設定・保存内容を保護してください。
利用するライブラリとモデルの条件・出典は `THIRD_PARTY.txt` と `LICENSES` に同梱します。
現在はコード署名なしです。
