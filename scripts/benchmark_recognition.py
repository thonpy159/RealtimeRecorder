"""Known text -> synthetic mic PCM -> production Channel/VAD/ASR -> character error rate.

This is not a claim about the user's real microphone or human speech accuracy.
"""
import argparse
import copy
from pathlib import Path
import sys
import json
import threading
import time
import unicodedata
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import soxr
from app.audio.microphone import MicrophoneAudioSource
from app.asr.recognizer import ReazonRecognizer, Recognizer
from app.asr.worker import ASRWorker
from app.config.settings import ROOT, load_settings
from app.pipeline import Channel
from app.records import Speaker
from scripts.diagnose import read_wav


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if unicodedata.category(c)[0] not in ('P', 'Z', 'S'))


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (x != y)))
        previous = current
    return previous[-1]


class SimulatedMicrophone(MicrophoneAudioSource):
    """Hardware adapter only is simulated. PortAudio callback and downstream code are real."""
    def __init__(self, samples, rate=48000, mode='normal'):
        super().__init__()
        self.sample_rate, self.channels = rate, 2
        samples = soxr.resample(samples, 16000, rate)
        samples = np.pad(samples, (rate // 2, rate * 2))
        gain = .06 if mode == 'quiet' else 1
        self.pcm = np.stack((samples * gain, samples * gain * (-1 if mode == 'opposite_phase' else 1)), axis=1).astype(np.float32)
        self.done = threading.Event()
        self.producer = None

    def open(self):
        pass

    def start(self):
        def produce():
            size = self.sample_rate // 50
            for i in range(0, len(self.pcm), size):
                while self.queue.full() and not self.closing.is_set():
                    time.sleep(.001)
                if self.closing.is_set():
                    break
                data = self.pcm[i:i + size]
                self._callback(data.tobytes(), len(data), {}, 0)
            self.done.set()
        self.producer = threading.Thread(target=produce, name='SyntheticMic', daemon=False)
        self.producer.start()

    def check(self):
        if self.error:
            raise self.error

    def stop(self):
        self.closing.set()
        if self.producer:
            self.producer.join()

    def close(self):
        self.stop()


def evaluate(model, references, mode='normal', threads=2, speaker=Speaker.ME, vad_overrides=None):
    config = load_settings()
    config['vad'].update(vad_overrides or {})
    rows = []
    for ref in references:
        results, errors = [], []
        wav = read_wav(ROOT / 'models' / 'evaluation' / ref['file'])
        worker = ASRWorker(model, {}, results.append, errors.append)
        source = SimulatedMicrophone(wav, mode=mode)
        channel = Channel(source, speaker, config['vad'], ROOT / 'models' / 'silero_vad.onnx',
                          worker, lambda *args: None, errors.append)
        worker.start()
        channel.start()
        try:
            assert channel.ready.wait(15) and not channel.start_error
            assert source.done.wait(60)
            # A stop drains PCM, resampler and VAD before draining the ASR queue.
            channel.request_stop()
            channel.join(120)
            assert not channel.is_alive()
            worker.drain()
        finally:
            channel.request_stop()
            channel.join()
            worker.shutdown()
        text = ''.join(r.raw_text for r in sorted(results, key=lambda r: r.speech_started_at))
        expected, actual = normalize(ref['text']), normalize(text)
        row = {'file': ref['file'], 'mode': mode, 'expected': ref['text'], 'actual': text,
               'errors': errors, 'edits': distance(expected, actual), 'characters': len(expected),
               'asr_s': sum(r.asr_processing_ms for r in results) / 1000,
               'segments': len(results), 'input_s': len(wav) / 16000}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=['reazon', 'kotoba', 'small', 'sensevoice'], default='sensevoice')
    parser.add_argument('--mode', choices=['normal', 'quiet', 'opposite_phase'], default='normal')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--report-tag', default='')
    args = parser.parse_args()
    references = json.loads((ROOT / 'models' / 'evaluation' / 'references.json').read_text('utf-8-sig'))
    if args.limit:
        references = references[:args.limit]
    factory = ReazonRecognizer if args.engine == 'reazon' else Recognizer
    started = time.perf_counter()
    model = factory(ROOT / 'models', 2) if args.engine == 'reazon' else factory(ROOT / 'models', 2, engine=args.engine)
    load_s = time.perf_counter() - started
    rows = evaluate(model, references, args.mode)
    report = {'engine': args.engine, 'mode': args.mode, 'load_s': load_s,
              'fixture_kind': 'Windows SAPI synthetic Japanese speech; not human microphone recording',
              'CER': sum(r['edits'] for r in rows) / sum(r['characters'] for r in rows), 'rows': rows}
    tag = ('-' + args.report_tag) if args.report_tag else ''
    path = ROOT / 'logs' / f'benchmark-{args.engine}-{args.mode}{tag}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print('CER:', report['CER'], flush=True)


if __name__ == '__main__':
    main()
