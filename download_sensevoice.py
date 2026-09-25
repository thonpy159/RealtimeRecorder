"""Official sherpa-onnx SenseVoice INT8 release download."""
import json
import os
import shutil
import tarfile
from download_models import ROOT, BASE, digest, download

NAME = 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17'
FILES = ('model.int8.onnx', 'tokens.txt')


def validate(root=ROOT / 'models'):
    folder = root / 'sensevoice'
    try:
        manifest = json.loads((folder / 'verified.json').read_text('utf-8'))
        for name in FILES:
            p = folder / name
            if p.stat().st_size != manifest[name]['size'] or digest(p) != manifest[name]['sha256']:
                raise ValueError(name)
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise RuntimeError('SenseVoiceモデルが不足・破損しています。setup.ps1 を実行してください。') from e
    return folder


def main():
    try:
        validate()
        print('SenseVoice model verified.')
        return
    except RuntimeError:
        pass
    folder = ROOT / 'models' / 'sensevoice'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / (NAME + '.tar.bz2')
    if not archive.exists():
        download(BASE + archive.name, archive)
    try:
        with tarfile.open(archive, 'r:bz2') as source:
            for member in source:
                name = member.name.rsplit('/', 1)[-1]
                if member.isfile() and name in FILES:
                    target = folder / name
                    temporary = folder / (name + '.part')
                    with source.extractfile(member) as data, temporary.open('wb') as output:
                        shutil.copyfileobj(data, output)
                    if temporary.stat().st_size != member.size:
                        raise RuntimeError('Incomplete model archive')
                    os.replace(temporary, target)
    except (tarfile.TarError, EOFError):
        archive.unlink(missing_ok=True)
        raise RuntimeError('モデルの圧縮ファイルが破損しています。setup.ps1 を再実行してください。')
    manifest = {name: {'size': (folder / name).stat().st_size, 'sha256': digest(folder / name)} for name in FILES}
    (folder / 'verified.json').write_text(json.dumps(manifest, indent=2), 'utf-8')
    validate()
    archive.unlink()
    print('SenseVoice model downloaded and verified.')


if __name__ == '__main__':
    main()
