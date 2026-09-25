$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$fixtureRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'models\evaluation'
New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null
$sentences = @(
    'あいうえお。',
    '今日はよろしくお願いします。',
    '前回のヒアリングから、何か変わったことはありますか。',
    '今月からテスト工程が増えて、作業量が多くなっています。',
    '残業時間にも影響していますか。',
    '来週の水曜日に、もう一度打ち合わせをお願いします。',
    'この問題について、担当者に確認してから連絡します。'
)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$records = @()
try {
    foreach ($voice in @('Microsoft Haruka Desktop', 'Microsoft Ichiro')) {
        $synth.SelectVoice($voice)
        for ($i = 0; $i -lt $sentences.Count; $i++) {
            $filename = (($voice -replace ' ', '_') + '-' + $i + '.wav')
            $synth.SetOutputToWaveFile((Join-Path $fixtureRoot $filename))
            $synth.Speak($sentences[$i])
            $synth.SetOutputToNull()
            $records += @{ file = $filename; text = $sentences[$i]; voice = $voice }
        }
    }
} finally { $synth.Dispose() }
$records | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $fixtureRoot 'references.json')
Write-Host ('Generated ' + $records.Count + ' synthetic Japanese fixtures; no microphone recording.')
