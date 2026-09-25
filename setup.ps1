$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectVenv = Join-Path $PSScriptRoot '.venv'
$projectPython = Join-Path $projectVenv 'Scripts\python.exe'
function Assert-Exit {
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}
if (Test-Path -LiteralPath $projectVenv) {
    if ((Get-Item -LiteralPath $projectVenv).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Project .venv must not be a junction or symbolic link to another environment.'
    }
    $valid = $false
    if (Test-Path -LiteralPath $projectPython) {
        & $projectPython -c "import sys,struct; assert sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8"
        $valid = $LASTEXITCODE -eq 0
    }
    if (-not $valid) {
        $resolved = [IO.Path]::GetFullPath($projectVenv)
        $expected = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '.venv'))
        if ($resolved -ne $expected) { throw 'Unsafe virtual environment path' }
        Move-Item -LiteralPath $resolved -Destination ($resolved + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    }
}
if (-not (Test-Path -LiteralPath $projectPython)) {
    $basePython = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $found = & py -3.11 -c "import sys,struct; assert struct.calcsize('P') == 8; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0) { $basePython = $found }
    }
    if (-not $basePython) {
        $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
        if (Test-Path -LiteralPath $candidate) { $basePython = $candidate }
    }
    if (-not $basePython) { throw 'Python 3.11 x64 is required. Install it and rerun setup.ps1.' }
    & $basePython -c "import sys,struct; assert sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8"
    Assert-Exit
    & $basePython -m venv $projectVenv
    Assert-Exit
}
& $projectPython -c "import sys,pathlib; print(sys.version); print(sys.executable); assert pathlib.Path(sys.prefix).resolve() == pathlib.Path('.venv').resolve()"
Assert-Exit
& $projectPython -m pip install --upgrade pip
Assert-Exit
$requirements = if (Test-Path -LiteralPath 'requirements-lock.txt') { 'requirements-lock.txt' } else { 'requirements.txt' }
& $projectPython -m pip install -r $requirements
Assert-Exit
& $projectPython download_models.py
Assert-Exit
& $projectPython download_sensevoice.py
Assert-Exit
& $projectPython download_accuracy_model.py --engine small
Assert-Exit
& $projectPython download_accuracy_model.py --engine kotoba
Assert-Exit
& $projectPython -c "import PySide6,pyaudiowpatch,sherpa_onnx,numpy,soxr; print('Imports OK')"
Assert-Exit
& $projectPython -m pytest -q
Assert-Exit
& $projectPython scripts\diagnose.py
Assert-Exit
& $projectPython -m pip freeze | Set-Content -Encoding UTF8 requirements-lock.txt
Assert-Exit
Write-Host 'Setup complete. Double-click run.bat to start.'
