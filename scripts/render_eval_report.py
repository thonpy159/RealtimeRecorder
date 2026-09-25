"""Build the human-speech verification report from measured JSON artifacts."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT/'logs'/name).read_text('utf-8-sig'))


def main():
    old=read('human-sensevoice-t2-holdout-pipeline.json')
    new=read('human-reazon-t2-holdout-pipeline.json')
    live=read('live-reazon-t2.json')
    live_old=read('live-sensevoice-t2.json')
    report='''# 日本語の実音声・即時表示の検証（2026-09-24〜25）

## 結論と変更

ローカル処理・このPC・発話終了後1〜3秒を目標とする表示を維持し、今回の比較では改善できました。標準をReazonSpeech INT8 / greedy search / CPU 2スレッドへ変更しました。9月18日のチャンネル選択、小音量補正、VAD先頭保護、UI改修は維持しています。初版の入力処理へ戻したものではありません。SenseVoiceは比較用として残します。

前回の合成音声14本ではモデル選定が不十分でした。今回の認識モデル候補は4種類、探索幅を含む6構成です。評価文を認識器へ与えず、用語辞書・個人向け調整・正解への特別な置換を使っていません。

## このPCと評価音声

- AMD Ryzen 5 5625U、6コア12スレッド、約16GB RAM。GPU・外部ASRは未使用。
- プロジェクト専用 `.venv` のPython 3.11.9。依存バージョンは `requirements-lock.txt`。
- [Common Voice 8 日本語](https://huggingface.co/datasets/japanese-asr/ja_asr.common_voice_8_0)と[ReazonSpeech評価用](https://huggingface.co/datasets/japanese-asr/ja_asr.reazonspeech_test)から各60本。人が話した読み上げ・放送音声で、本人の声ではありません。
- 各コーパス先頭から重複文を除いた60本を使用。最初の16本ずつ、計32本を構成選定用にし、残る44本ずつ、計88本を選定後の確認に使用しました。無作為抽出や話者単位の完全分離ではありません。
- Hugging Face viewerのMP3派生音声を16kHzへデコード。原音の無圧縮データとは異なります。ファイルごとのSHA-256、データセットrevision、正解文、分割は `models/human-evaluation/references.json`。
- CERはNFKC正規化後に空白・句読点・記号を除いた文字編集距離です。漢字／かな・数字表記の違い、余分な語も誤りに含みます。意味の誤りだけを数えた割合ではありません。

## 構成選定：同じ32本をモデルへ直接入力

| 構成 | CPUスレッド | 文字誤り率 | 認識処理 p95 | RTF |
|---|---:|---:|---:|---:|
'''
    candidates=[('SenseVoice','human-sensevoice-t2-development.json'),
        ('ReazonSpeech greedy','human-reazon-t4-development.json'),
        ('ReazonSpeech beam 4','human-reazon-4-t4-development.json'),
        ('ReazonSpeech beam 8','human-reazon-8-t4-development.json'),
        ('Whisper small beam 1','human-small-1-t4-development.json'),
        ('Kotoba beam 1','human-kotoba-1-t4-development.json')]
    for label,path in candidates:
        d=read(path); s=d['summary']
        report+=f"| {label} | {d['threads']} | {s['CER']:.2%} | {s['asr_p95_s']:.3f}秒 | {s['RTF']:.3f} |\n"
    report+='''
RTFは処理時間÷音声時間。1を超える構成は単一入力でも処理が追いつきません。SenseVoiceは現設定の2スレッド、比較候補は4スレッドです。速度を厳密に同一スレッド数で比較した表ではありません。採用候補は下記で2スレッドに戻し、実入力処理と実時間表示を確認しました。

ReazonSpeechの探索幅を増やしても誤りは減りませんでした。Whisper smallとKotobaは探索幅1にしても、精度・待ち時間の両面で今回の採用候補を上回りませんでした。大きいモデルへの変更だけでは条件を満たしませんでした。

## 選定後の88本：本番のマイク入力処理を通した比較

48kHz・2ch・20msブロックとして、マイクコールバック→入力キュー→チャンネル選択／増幅／リサンプル→独立Silero VAD→共通ASRワーカーへ入力。両構成で同じ音声・設定・2スレッドです。この試験は高速投入のため、表示遅延は次節で別途測定しています。

| 指標 | 変更前 SenseVoice | 採用 ReazonSpeech |
|---|---:|---:|
'''
    a=old['summary']; b=new['summary']
    report+=f"| 文字誤り率 | {a['CER']:.2%} | {b['CER']:.2%} |\n"
    report+=f"| 編集距離 / 正解文字数 | {a['edits']} / {a['characters']} | {b['edits']} / {b['characters']} |\n"
    report+=f"| 認識処理 p95 | {a['asr_p95_s']:.3f}秒 | {b['asr_p95_s']:.3f}秒 |\n"
    report+=f"| RTF | {a['RTF']:.3f} | {b['RTF']:.3f} |\n"
    for key,label in [('ja_asr.common_voice_8_0','Common Voice 44本 CER'),('ja_asr.reazonspeech_test','放送音声44本 CER')]:
        report+=f"| {label} | {old['datasets'][key]['CER']:.2%} | {new['datasets'][key]['CER']:.2%} |\n"
    report+=f"\n今回の88本では誤りが **{1-b['edits']/a['edits']:.1%}減少**しました。個別の正解・出力・誤り数を `logs/human-*-holdout-pipeline.json` に保持しています。\n"
    report+='''
モデル単体の成績と入力処理込みの成績は同じではありません。選定用32本のReazonSpeechも入力処理込みでは15.10%でした。VADによる切り分けや無音の付加で結果が変わります。モデル単体の5.98%をアプリ全体の精度として報告していません。

## 追加の未使用80音声と、採用しなかった変更

連続入力で声の取りこぼしがあったため、相手側の増幅追加と、発話検出の感度変更も比較しました。増幅追加は選定用32本で誤りが増えたため不採用です。

感度を0.35から0.15にすると選定用音声では改善しましたが、新たに取得した80本（各コーパス行80以降、各40本）では改善が再現しませんでした。この80本は最初の120本と音声ハッシュ・正解文の重複がありません。最終設定は感度0.35のままです。

| 相手音声経路・追加80本 | 編集距離 / 1860文字 | CER |
|---|---:|---:|
| 変更前 SenseVoice、感度0.35 | 438 / 1860 | 23.55% |
| 採用 ReazonSpeech、感度0.35 | 211 / 1860 | 11.34% |
| 不採用 ReazonSpeech、感度0.15 | 212 / 1860 | 11.40% |

根拠は `logs/human-*-confirmation.json`。追加のモデル変更効果は、この80本で文字誤り約51.8%減でした。最初の88本とは別の比較です。

## 雑音対策と回帰確認

標準感度でも、小さな定常ホワイトノイズを「あれ」と認識する例を再現しました。ReazonSpeechへ渡す前に、エネルギー変動とスペクトルの平坦さから、持続する定常広帯域雑音を除外する処理を追加しました。短い語の文字列を消す処理や、誤認識語への特別な置換はありません。

- 無音、大小のホワイトノイズ、低周波ハム、クリック音を各10秒、マイク／相手の両経路に投入。最終の標準設定では10条件すべて非発話出力0件。
- 対策前後で公開実音声200本を本番入力処理から比較し、認識文字列の変更0件。元の認識誤りが0件という意味ではありません。
- 自動テスト50件成功。短い有声音、弱い有声音、変動する無声音、VADの前後無音を含む雑音判定も確認。
- 検証した雑音以外や、すべてのささやき声の安全性を保証するものではありません。

根拠: `logs/nonspeech-controls-before.json`、`logs/nonspeech-controls.json`、`logs/final-validation.json`。感度を上げた候補（閾値0.15）の別試験は不採用の検証記録として残しています。

以前の合成音声14本も、通常音量・小音量・逆位相で再実行しました。CERはそれぞれ1.57%、2.76%、1.57%でした。SenseVoiceの合成音声成績0.79%を上回る誤り数ですが、人の声の比較を優先して選定しました。正解との漢字／かな表記差も含む数値です。

## 2入力同時・実時間・GUI表示

同じ公開確認用音声を、マイク相当とLoopback相当の2経路へ同時に20msごとに実時間投入しました。単一ASRモデルと共通ワーカー、実MainWindowとQtの同期再描画まで通しています。物理マイクの音響環境は再現していません。

遅延の起点は本番VADが返す発話終了時刻、終点は文字起こし欄の同期再描画後です。VAD待ち、キュー待ち、ASR処理、GUI更新を含みます。人が付けた発話終了ラベルによる測定ではありません。

| 指標 | 変更前 SenseVoice | 採用 ReazonSpeech |
|---|---:|---:|
'''
    for key,label in [('clips','音声数'),('latency_p50_s','表示遅延 中央値（秒）'),('latency_p95_s','表示遅延 p95（秒）'),('latency_max_s','表示遅延 最大（秒）'),('peak_queue','観測した認識待ちキュー最大件数')]:
        report+=f"| {label} | {live_old[key]:.3f} | {live[key]:.3f} |\n"
    live_cer=lambda r:sum(x['edits'] for x in r['speakers'].values())/sum(x['characters'] for x in r['speakers'].values())
    report+=f"| 2入力合計 CER | {live_cer(live_old):.2%} | {live_cer(live):.2%} |\n"
    for key,label in [('ME','マイク相当 CER'),('OTHER','Loopback相当 CER')]:
        report+=f"| {label} | {live_old['speakers'][key]['CER']:.2%} | {live['speakers'][key]['CER']:.2%} |\n"
    report+=f"\n採用構成: エラー{len(live['errors'])}件、残存ワーカー{len(live['remaining_threads'])}件。実時間{live['wall_s']:.1f}秒、プロセスCPU時間{live['process_cpu_s']:.1f}秒。キュー長は約5ms間隔の観測値です。厳密な瞬間最大値ではありません。\n"
    report+='''
根拠: `logs/live-reazon-t2.json`、`logs/live-sensevoice-t2.json`。マイク相当とLoopback相当には異なるコーパスを流しているため、この表の話者間のCER差を入力機器の性能差と解釈できません。

## 最終起動確認

2026-09-25に自動テスト50件成功、Python構文チェック、実GUIの起動・ReazonSpeech実ロード・正常終了を確認しました。録音開始なし、エラー0件、残存ワーカー0件。根拠は `logs/final-ready.json`。この起動確認時点ではマイク候補0件、Loopback候補3件でした。実機マイクからの発話精度を今回確認したという意味ではありません。

## 制限と再現方法

今回確認した候補・音声での改善であり、日本語全体の精度上限を証明したものではありません。自然な実会議全体、遠距離の反響、雑音、全話者、Google Meetと同時通話中の長時間性能は未検証です。未検証の大規模モデルがこのPCで条件を満たすとも、満たさないとも断定していません。ReazonSpeechは句読点が少ない出力になります。

公開音声の取得だけネットワークを使います。認識・再生試験はローカルです。実利用の録音保存・外部送信・自動文字保存は追加していません。

```powershell
.\\.venv\\Scripts\\python.exe scripts\\fetch_japanese_eval.py
.\\.venv\\Scripts\\python.exe scripts\\benchmark_human.py --engine reazon --threads 2 --split holdout --pipeline
.\\.venv\\Scripts\\python.exe scripts\\benchmark_human.py --engine sensevoice --threads 2 --split holdout --pipeline
.\\.venv\\Scripts\\python.exe scripts\\benchmark_live_replay.py --engine reazon --threads 2 --count 16
.\\.venv\\Scripts\\python.exe scripts\\benchmark_live_replay.py --engine sensevoice --threads 2 --count 16
.\\.venv\\Scripts\\python.exe -m pytest -q
```

既存の `config.json` は `logs/config-before-human-evaluation.json` に保管しました。現在の設定はReazonSpeech、CPU 2スレッドです。起動中の旧インスタンスはモデルを保持するため、変更は次の起動から適用されます。
'''
    (ROOT/'VERIFICATION-JAPANESE.md').write_text(report,'utf-8')


if __name__=='__main__': main()
