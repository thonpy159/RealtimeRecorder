"""Assemble a minimal portable release without local config, logs or recordings."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from download_models import ROOT, MODEL_NAME, FILES, validate_models
from app.config.settings import DEFAULTS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-build',action='store_true')
    parser.add_argument('--zip',action='store_true')
    args=parser.parse_args()
    validate_models()
    if not args.skip_build:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',str(ROOT/'recorder.spec')],cwd=ROOT,check=True)
    dest=ROOT/'dist/RealtimeRecorder'
    wanted=[f'{MODEL_NAME}/{name}' for name in FILES]+['silero_vad.onnx']
    for name in wanted+[f'{MODEL_NAME}/test_wavs/1.wav']:
        target=dest/'models'/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'models'/name,target)
    manifest=json.loads((ROOT/'models/manifest.json').read_text('utf-8'))
    (dest/'models/manifest.json').write_text(json.dumps({k:manifest[k] for k in wanted},indent=2),'utf-8')
    licenses=dest/'LICENSES'; licenses.mkdir(exist_ok=True)
    shutil.copytree(ROOT/'packaging/licenses',licenses,dirs_exist_ok=True)
    versions={}
    for name in ['PySide6_Essentials','shiboken6','sherpa-onnx','sherpa-onnx-core','PyAudioWPatch','numpy','soxr']:
        d=metadata.distribution(name); versions[name]=d.version
        for path in d.files or []:
            if any(word in str(path).lower() for word in ['license','copying','notice']) and d.locate_file(path).is_file():
                target=licenses/name/str(path)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(d.locate_file(path),target)
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.exists(): shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
    (licenses/'versions.json').write_text(json.dumps(versions,indent=2),'utf-8')
    shutil.copy2(ROOT/'packaging/README.txt',dest/'はじめに.txt')
    shutil.copy2(ROOT/'packaging/THIRD_PARTY.txt',dest/'THIRD_PARTY.txt')
    shutil.copy2(ROOT/'LICENSE',dest/'LICENSE')
    # Never ship the developer's runtime settings.
    (dest/'config.json').write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    if args.zip:
        archive=ROOT/'dist/RealtimeRecorder-Windows-x64.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for path in sorted(dest.rglob('*')):
                relative=path.relative_to(dest)
                if path.is_file() and relative.parts[0] not in ('logs',):
                    z.write(path,str(Path('RealtimeRecorder')/relative))
        print('ZIP:',archive,'bytes:',archive.stat().st_size)
    print('Folder:',dest)
    print('Folder bytes:',sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()))


if __name__=='__main__': main()
