"""Download only public evaluation audio; never uploads local audio."""
import concurrent.futures
import argparse
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'models' / 'human-evaluation'
DATASETS = ['ja_asr.common_voice_8_0', 'ja_asr.reazonspeech_test']


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--offset',type=int,default=0)
    parser.add_argument('--count',type=int,default=60)
    parser.add_argument('--development',type=int,default=16)
    parser.add_argument('--manifest',default='references.json')
    args=parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for dataset in DATASETS:
        query = urllib.parse.urlencode(dict(dataset='japanese-asr/' + dataset,
                                             config='default', split='test', offset=args.offset,
                                             length=min(100,args.count+20)))
        data = json.loads(get('https://datasets-server.huggingface.co/rows?' + query))
        seen = set()
        selected = []
        for entry in data['rows']:
            text = entry['row']['transcription']
            if text in seen:
                continue
            seen.add(text)
            index = entry['row_idx']
            source = entry['row']['audio'][0]['src']
            selected.append(dict(dataset=dataset, index=index, text=text,
                                 file=f'{dataset}-{index}.mp3',
                                 source=source, revision=source.split('/--/')[1],
                                 split='development' if len(selected) < args.development else 'holdout'))
            if len(selected) == args.count:
                break
        def fetch(row):
            path = DEST / row['file']
            if not path.exists():
                path.write_bytes(get(row['source']))
            row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            row['source'] = 'https://huggingface.co/datasets/japanese-asr/' + dataset
            return row
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            rows.extend(pool.map(fetch, selected))
        print(dataset, len(selected), flush=True)
    (DEST / args.manifest).write_text(json.dumps(rows, ensure_ascii=False, indent=2), 'utf-8')
    print('Downloaded', len(rows), 'public human speech clips.', flush=True)


if __name__ == '__main__':
    main()
