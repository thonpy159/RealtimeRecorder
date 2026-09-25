from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from uuid import uuid4
import numpy as np


class Speaker(str, Enum):
    ME = 'ME'
    OTHER = 'OTHER'

    @property
    def label(self):
        return '自分' if self == Speaker.ME else '相手'


@dataclass
class Utterance:
    speaker: Speaker
    speech_started_at: datetime
    speech_ended_at: datetime
    audio: np.ndarray = field(repr=False)
    ended_monotonic: float = 0
    id: str = field(default_factory=lambda: str(uuid4()))
    audio_duration_ms: float = 0
    raw_text: str = ''
    display_text: str = ''
    asr_processing_ms: float = 0
    total_latency_ms: float = 0


def replace_terms(text, dictionary):
    if not dictionary:
        return text
    pattern = '|'.join(re.escape(k) for k in sorted(dictionary, key=len, reverse=True))
    return re.sub(pattern, lambda m: dictionary[m.group()], text)


def format_japanese(text):
    # SenseVoice can insert token-separator spaces in Japanese. Preserve spaces
    # in English names/phrases; this is typography, never a recognition rewrite.
    jp = r'\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff'
    return re.sub(rf'(?<=[{jp}])[ \t]+(?=[{jp}、。！？])', '', text)


def ordered(records):
    return sorted(records, key=lambda r: (r.speech_started_at, r.id))


def markdown(records):
    rows = ordered(records)
    day = rows[0].speech_started_at.date() if rows else datetime.now().date()
    text = f'# リアルタイムレコーダー\n\n日時: {day}\n'
    for r in rows:
        text += f'\n## {r.speech_started_at:%H:%M:%S} {r.speaker.label}\n\n{r.display_text}\n'
    return text
