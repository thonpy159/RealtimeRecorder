import copy
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
DEFAULTS = {
    'asr_engine': 'reazon',
    'asr_threads': 2,
    'vad': {'threshold': 0.35, 'silence_ms': 800, 'min_speech_ms': 180,
            'pre_roll_ms': 500, 'post_roll_ms': 200, 'max_speech_s': 20},
    'dictionary': {'エーアイ': 'AI', 'エスエヌエス': 'SNS',
                   'ユーアールエル': 'URL', 'ユーチューブ': 'YouTube', 'グーグル': 'Google'},
    'ui': {'font_size': 14, 'auto_scroll': True},
    'asr_queue_size': 32,
}


def save_settings(settings, path=ROOT / 'config.json'):
    path = Path(path)
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), 'utf-8')
    os.replace(temp, path)


def load_settings(path=ROOT / 'config.json'):
    path = Path(path)
    data = copy.deepcopy(DEFAULTS)
    if not path.exists():
        save_settings(data, path)
        return data
    try:
        loaded = json.loads(path.read_text('utf-8-sig'))
        if not isinstance(loaded, dict):
            raise ValueError('設定はJSONオブジェクトが必要です')
        for key, value in loaded.items():
            if key in ('vad', 'ui'):
                data[key].update(value)
            else:
                data[key] = value
        if type(data['asr_threads']) is not int or data['asr_threads'] not in (1, 2, 4):
            raise ValueError('asr_threads は 1, 2, 4 のいずれかです')
        if data['asr_engine'] not in ('reazon', 'sensevoice', 'small', 'kotoba'):
            raise ValueError('asr_engine は reazon, sensevoice, small, kotoba のいずれかです')
        limits = {'threshold': (0.05, 0.95), 'silence_ms': (100, 3000),
                  'min_speech_ms': (100, 1000), 'pre_roll_ms': (0, 1000),
                  'post_roll_ms': (0, 500), 'max_speech_s': (2, 30)}
        for key, (lo, hi) in limits.items():
            v = data['vad'][key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError(f'vad.{key} は {lo}～{hi} にしてください')
        if data['vad']['post_roll_ms'] > data['vad']['silence_ms']:
            raise ValueError('post_roll_ms は silence_ms 以下にしてください')
        d = data['dictionary']
        if not isinstance(d, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in d.items()):
            raise ValueError('dictionary は空でない文字列キーと文字列値が必要です')
        if type(data['asr_queue_size']) is not int or not 2 <= data['asr_queue_size'] <= 128:
            raise ValueError('asr_queue_size は 2～128 にしてください')
        if type(data['ui']['font_size']) is not int or not 9 <= data['ui']['font_size'] <= 30:
            raise ValueError('font_size は 9～30 にしてください')
        if type(data['ui']['auto_scroll']) is not bool:
            raise ValueError('auto_scroll は true または false です')
    except (OSError, ValueError, TypeError, KeyError) as e:
        raise ValueError(f'config.json を読み込めません: {e}（元ファイルは保持しています）') from e
    return data
