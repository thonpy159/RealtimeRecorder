"""Official sherpa-onnx release downloader; no external archive utilities required."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time
import urllib.request
import sys

ROOT = Path(__file__).resolve().parent
MODEL_NAME = 'sherpa-onnx-zipformer-ja-reazonspeech-2024-08-01'
FILES = ('tokens.txt', 'encoder-epoch-99-avg-1.int8.onnx',
         'decoder-epoch-99-avg-1.onnx', 'joiner-epoch-99-avg-1.int8.onnx')
BASE = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_models(root=ROOT / 'models'):
    manifest = root / 'manifest.json'
    try:
        entries = json.loads(manifest.read_text('utf-8'))
        required = [f'{MODEL_NAME}/{f}' for f in FILES] + ['silero_vad.onnx']
        for name in required:
            p = root / name
            info = entries[name]
            if not p.is_file() or p.stat().st_size != info['size'] or digest(p) != info['sha256']:
                raise ValueError(name)
    except (OSError, ValueError, KeyError, TypeError) as e:
        if getattr(sys, 'frozen', False):
            raise RuntimeError('モデルが不足または破損しています。配布ZIPをフォルダごと展開し直してください。') from e
        raise RuntimeError('モデルが不足または破損しています。setup.ps1 を再実行してください。') from e


def download(url, path):
    temporary = path.with_suffix(path.suffix + '.part')
    print('Downloading:', url, flush=True)
    for attempt in range(6):
        offset = temporary.stat().st_size if temporary.exists() else 0
        headers = {'User-Agent': 'realtime-recorder-setup'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                resumed = response.status == 206
                if resumed and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                    raise RuntimeError('Invalid resume response')
                if not resumed:
                    offset = 0
                expected = response.headers.get('Content-Length')
                size = 0
                last = 0
                with temporary.open('ab' if resumed else 'wb') as out:
                    while chunk := response.read(1024 * 1024):
                        out.write(chunk)
                        size += len(chunk)
                        if size - last >= 50 * 1024 * 1024:
                            print(f'  {(offset + size) / 1024**2:.0f} MiB', flush=True)
                            last = size
                if expected and size != int(expected):
                    raise RuntimeError('ダウンロードが途中で終了しました')
            os.replace(temporary, path)
            return
        except (OSError, RuntimeError) as e:
            if attempt == 5:
                raise
            print(f'Download interrupted; resuming ({attempt + 1}/5): {e}', flush=True)
            time.sleep(2)


def main():
    root = ROOT / 'models'
    root.mkdir(exist_ok=True)
    try:
        validate_models(root)
        print('Models verified (SHA-256).')
        return
    except RuntimeError:
        pass
    archive = root / (MODEL_NAME + '.tar.bz2')
    if not archive.exists():
        download(BASE + archive.name, archive)
    try:
        with tarfile.open(archive, 'r:bz2') as tar:
            for member in tar:
                path = PurePosixPath(member.name)
                if not member.isfile() or len(path.parts) < 2 or path.parts[0] != MODEL_NAME:
                    continue
                if '..' in path.parts or path.is_absolute():
                    raise RuntimeError('Unsafe archive entry')
                if path.name not in FILES and not (len(path.parts) == 3 and path.parts[1] == 'test_wavs' and path.suffix == '.wav'):
                    continue
                target = root.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix(target.suffix + '.part')
                with tar.extractfile(member) as source, temp.open('wb') as out:
                    shutil.copyfileobj(source, out)
                if temp.stat().st_size != member.size:
                    raise RuntimeError('Incomplete archive member')
                os.replace(temp, target)
    except (tarfile.TarError, EOFError, OSError):
        archive.unlink(missing_ok=True)
        raise
    download(BASE + 'silero_vad.onnx', root / 'silero_vad.onnx')
    entries = {}
    for name in [f'{MODEL_NAME}/{f}' for f in FILES] + ['silero_vad.onnx']:
        path = root / name
        if path.stat().st_size < 100:
            raise RuntimeError('Invalid model: ' + name)
        entries[name] = {'size': path.stat().st_size, 'sha256': digest(path)}
    temp = root / 'manifest.json.tmp'
    temp.write_text(json.dumps(entries, indent=2), 'utf-8')
    os.replace(temp, root / 'manifest.json')
    validate_models(root)
    archive.unlink(missing_ok=True)
    print('Models downloaded and verified.', flush=True)


if __name__ == '__main__':
    main()
