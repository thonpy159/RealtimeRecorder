"""Download official Kotoba weights. Never sends local audio or transcript data."""
import json
import argparse
import hashlib
from pathlib import Path
import urllib.request
from download_models import ROOT, digest, download

MODELS = {'small': ('Systran/faster-whisper-small', 'whisper-small'),
          'kotoba': ('kotoba-tech/kotoba-whisper-v2.0-faster', 'kotoba-whisper-v2.0-faster')}
def required(engine):
    return ('config.json', 'model.bin', 'tokenizer.json',
            'vocabulary.txt' if engine == 'small' else 'vocabulary.json',
            *(('preprocessor_config.json',) if engine == 'kotoba' else ()))


def validate(root=ROOT / 'models', engine='small'):
    _, DIRECTORY = MODELS[engine]
    folder = root / DIRECTORY
    try:
        manifest = json.loads((folder / 'verified.json').read_text('utf-8'))
        for name in required(engine):
            path = folder / name
            entry = manifest['files'][name]
            if path.stat().st_size != entry['size'] or digest(path) != entry['sha256']:
                raise ValueError(name)
    except (OSError, KeyError, ValueError, TypeError) as e:
        raise RuntimeError('高精度モデルが不足・破損しています。setup.ps1 を実行してください。') from e
    return folder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=MODELS, default='small')
    args = parser.parse_args()
    REPO, DIRECTORY = MODELS[args.engine]
    try:
        validate(engine=args.engine)
        print(args.engine + ' model verified.')
        return
    except RuntimeError:
        pass
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}?blobs=true', timeout=60) as r:
        metadata = json.load(r)
    revision = metadata['sha']
    remote = {f['rfilename']: f for f in metadata['siblings']}
    folder = ROOT / 'models' / DIRECTORY
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {'repo': REPO, 'revision': revision, 'files': {}}
    for name in (*required(args.engine), 'README.md'):
        path = folder / name
        size = remote[name]['size']
        expected = remote[name].get('lfs', {}).get('sha256')
        def valid_remote_file():
            if not path.exists() or path.stat().st_size != size:
                return False
            if expected:
                return digest(path) == expected
            content = path.read_bytes()
            return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest() == remote[name]['blobId']
        if not valid_remote_file():
            download(f'https://huggingface.co/{REPO}/resolve/{revision}/{name}', path)
        sha = digest(path)
        if not valid_remote_file():
            raise RuntimeError(f'Model integrity check failed: {name}')
        manifest['files'][name] = {'size': size, 'sha256': sha}
    (folder / 'verified.json').write_text(json.dumps(manifest, indent=2), 'utf-8')
    validate(engine=args.engine)
    print(args.engine + ' model downloaded and verified.', flush=True)


if __name__ == '__main__':
    main()
