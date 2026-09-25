import copy
from datetime import datetime, timedelta, timezone
import json
from queue import Full
import time
import numpy as np
import pytest
from app.records import Speaker, Utterance, ordered, replace_terms, markdown
from app.asr.worker import ASRWorker
from app.audio.preprocess import AudioPreprocessor
from app.config.settings import DEFAULTS, load_settings
from app.vad.detector import SampleRing
from download_models import validate_models


def item(speaker=Speaker.ME, offset=0):
    now = datetime.now(timezone.utc) + timedelta(seconds=offset)
    return Utterance(speaker, now, now + timedelta(seconds=1), np.ones(16000, np.float32), time.monotonic())


@pytest.mark.parametrize('speaker,label', [(Speaker.ME, '自分'), (Speaker.OTHER, '相手')])
def test_labels(speaker, label):
    assert speaker.label == label


@pytest.mark.parametrize('text,expected', [('エーアイです', 'AIです'), ('グーグルを使う', 'Googleを使う'), ('未登録', '未登録')])
def test_dictionary_in_sentence(text, expected):
    assert replace_terms(text, DEFAULTS['dictionary']) == expected


def test_dictionary_longest_and_no_recursive_replacement():
    assert replace_terms('ABC A', {'A': 'B', 'ABC': 'A', 'B': 'C'}) == 'A B'


def test_config_default_created(tmp_path):
    p = tmp_path / 'config.json'
    assert load_settings(p) == DEFAULTS
    assert json.loads(p.read_text('utf-8')) == DEFAULTS


@pytest.mark.parametrize('contents', ['{', '[]', '{"asr_threads":12}', '{"vad":{"threshold":2}}', '{"dictionary":{"":"x"}}'])
def test_bad_config_preserved(tmp_path, contents):
    p = tmp_path / 'config.json'
    p.write_text(contents, 'utf-8')
    with pytest.raises(ValueError):
        load_settings(p)
    assert p.read_text('utf-8') == contents


def test_config_partial(tmp_path):
    p = tmp_path / 'config.json'
    p.write_text('{"asr_threads":4,"vad":{"silence_ms":800}}', 'utf-8')
    data = load_settings(p)
    assert data['asr_threads'] == 4 and data['vad']['silence_ms'] == 800
    assert data['vad']['pre_roll_ms'] == 500


def test_downmix():
    x = np.array([[1, -1], [.8, .2]], np.float32)
    np.testing.assert_allclose(AudioPreprocessor(16000, 2).process(x), [0, .5])


@pytest.mark.parametrize('rate', [44100, 48000])
def test_resampling_chunk_continuity_and_length(rate):
    t = np.arange(rate) / rate
    x = np.sin(2 * np.pi * 500 * t).astype(np.float32)
    expected = AudioPreprocessor(rate, 1).process(x, final=True)
    p = AudioPreprocessor(rate, 1)
    actual = np.concatenate([p.process(x[i:i+997]) for i in range(0, len(x), 997)] + [p.process(b'', final=True)])
    assert len(actual) == 16000
    assert actual.dtype == np.float32
    np.testing.assert_allclose(actual, expected, atol=1e-6)


def test_resampling_rejects_aliasing():
    t = np.arange(48000) / 48000
    x = np.sin(2 * np.pi * 12000 * t).astype(np.float32)
    output = AudioPreprocessor(48000, 1).process(x, final=True)
    assert np.sqrt(np.mean(output[100:-100] ** 2)) < .001


def test_order_uses_started_at():
    early, late = item(), item(offset=4)
    assert ordered([late, early]) == [early, late]
    early.display_text, late.display_text = '最初', '最後'
    text = markdown([late, early])
    assert text.index('最初') < text.index('最後')


def test_worker_preserves_raw_timestamps_releases_audio_and_recovers():
    class Recognizer:
        calls = 0
        def recognize(self, audio):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError('simulated ASR error')
            return 'エーアイです'
    output, errors = [], []
    w = ASRWorker(Recognizer(), DEFAULTS['dictionary'], output.append, errors.append)
    first, second = item(), item(Speaker.OTHER)
    saved = second.speech_started_at, second.speech_ended_at, second.id
    w.start()
    w.submit(first)
    w.submit(second)
    w.drain()
    assert w.is_alive()
    w.shutdown()
    assert not w.is_alive()
    assert len(errors) == 1 and output == [second]
    assert second.raw_text == 'エーアイです' and second.display_text == 'AIです'
    assert saved == (second.speech_started_at, second.speech_ended_at, second.id)
    assert len(first.audio) == len(second.audio) == 0
    assert second.audio_duration_ms == 1000 and second.asr_processing_ms >= 0


def test_queue_bounded():
    w = ASRWorker(None, {}, lambda x: None, lambda e: None, queue_size=2)
    w.submit(item())
    w.submit(item())
    with pytest.raises(Full):
        w.submit(item())


def test_short_empty_utterance_skipped():
    output = []
    w = ASRWorker(None, {}, output.append, output.append)
    short = item()
    short.audio = np.zeros(10, np.float32)
    w.start()
    w.submit(short)
    w.shutdown()
    assert output == [] and len(short.audio) == 0


def test_model_missing(tmp_path):
    with pytest.raises(RuntimeError, match='モデル'):
        validate_models(tmp_path)


def test_model_manifest_corrupt(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}', 'utf-8')
    with pytest.raises(RuntimeError):
        validate_models(tmp_path)


def test_ring_wrap_preserves_pre_roll():
    r = SampleRing(10)
    r.append(np.arange(8, dtype=np.float32))
    r.append(np.arange(8, 16, dtype=np.float32))
    np.testing.assert_array_equal(r.get(5, 14), np.arange(6, 14))
