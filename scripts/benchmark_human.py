"""Reproducible CPU evaluation on public human Japanese speech, no reference prompts."""
import argparse
import json
from pathlib import Path
import sys
import time
import wave
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from faster_whisper.audio import decode_audio
from scripts.benchmark_recognition import normalize, distance
from app.asr.recognizer import Recognizer
from download_models import FILES, MODEL_NAME
import sherpa_onnx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'models' / 'human-evaluation'


def audio(row):
    path = DATA / row['file']
    x = decode_audio(str(path), sampling_rate=16000)
    wav = path.with_suffix('.wav')
    if not wav.exists():
        with wave.open(str(wav), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    return x


def make_model(engine, threads):
    if engine == 'reazon':
        return Recognizer(ROOT / 'models', threads, engine)
    if engine.startswith('reazon'):
        p = ROOT / 'models' / MODEL_NAME
        beam = int(engine.split('-')[-1]) if '-' in engine else 1
        model = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=str(p / FILES[0]), encoder=str(p / FILES[1]),
            decoder=str(p / FILES[2]), joiner=str(p / FILES[3]), num_threads=threads,
            decoding_method='modified_beam_search' if beam > 1 else 'greedy_search',
            max_active_paths=beam, provider='cpu', model_type='transducer')
        class Adapter:
            def recognize(self, x):
                stream = model.create_stream(); stream.accept_waveform(16000, x)
                model.decode_stream(stream)
                return stream.result.text.strip()
        return Adapter()
    if engine.startswith(('small-', 'kotoba-')):
        from faster_whisper import WhisperModel
        from download_accuracy_model import validate
        name, beam = engine.split('-')
        model = WhisperModel(str(validate(ROOT / 'models', name)), device='cpu',
                             compute_type='int8', cpu_threads=threads, num_workers=1,
                             local_files_only=True)
        class Adapter:
            def recognize(self, x):
                segments, _ = model.transcribe(x, language='ja', beam_size=int(beam),
                    temperature=0., condition_on_previous_text=False, vad_filter=False,
                    without_timestamps=True)
                return ''.join(s.text for s in segments).strip()
        return Adapter()
    return Recognizer(ROOT / 'models', threads, engine)


def summary(rows):
    chars = sum(r['characters'] for r in rows)
    duration = sum(r['audio_s'] for r in rows)
    return dict(samples=len(rows), characters=chars, edits=sum(r['edits'] for r in rows),
                CER=sum(r['edits'] for r in rows)/chars,
                audio_s=duration, asr_s=sum(r['asr_s'] for r in rows),
                RTF=sum(r['asr_s'] for r in rows)/duration,
                asr_p95_s=float(np.percentile([r['asr_s'] for r in rows], 95)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine', default='sensevoice')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--split', choices=['development','holdout','all'], default='development')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--pipeline', action='store_true')
    parser.add_argument('--input', choices=['ME','OTHER'], default='ME')
    parser.add_argument('--boost-loopback', action='store_true')
    parser.add_argument('--vad-threshold', type=float)
    parser.add_argument('--manifest', default='references.json')
    parser.add_argument('--tag', default='')
    args=parser.parse_args()
    refs=json.loads((DATA/args.manifest).read_text('utf-8'))
    refs=[r for r in refs if args.split=='all' or r['split']==args.split]
    if args.limit: refs=refs[:args.limit]
    inputs=[audio(r) for r in refs]
    t=time.perf_counter(); model=make_model(args.engine,args.threads); load=time.perf_counter()-t
    rows=[]
    if args.pipeline:
        from scripts.benchmark_recognition import evaluate
        from app.records import Speaker
        if args.boost_loopback:
            import app.pipeline
            from app.audio.preprocess import AudioPreprocessor
            class Boosted(AudioPreprocessor):
                def __init__(self,*a,**kw):
                    # Replay has two identical channels, so microphone selection
                    # equals downmix here; only its gain behavior differs.
                    kw['microphone']=True
                    super().__init__(*a,**kw)
            app.pipeline.AudioPreprocessor=Boosted
        converted = [dict(file=str((DATA/r['file']).with_suffix('.wav')), text=r['text']) for r in refs]
        overrides={} if args.vad_threshold is None else {'threshold':args.vad_threshold}
        evaluated = evaluate(model, converted, speaker=Speaker(args.input), vad_overrides=overrides)
        for ref, result in zip(refs, evaluated):
            rows.append(dict(file=ref['file'], dataset=ref['dataset'], expected=ref['text'],
                             actual=result['actual'], edits=result['edits'], characters=result['characters'],
                             asr_s=result['asr_s'], audio_s=result['input_s'],
                             segments=result['segments'], errors=result['errors']))
    for ref,x in zip(refs,inputs):
        if args.pipeline:
            break
        t=time.perf_counter(); actual=model.recognize(x); elapsed=time.perf_counter()-t
        expected=normalize(ref['text']); result=normalize(actual)
        rows.append(dict(file=ref['file'],dataset=ref['dataset'],expected=ref['text'],actual=actual,
                         edits=distance(expected,result),characters=len(expected),
                         asr_s=elapsed,audio_s=len(x)/16000))
        print(args.engine,len(rows),'edits',rows[-1]['edits'],'asr',round(elapsed,3),flush=True)
    report=dict(engine=args.engine,threads=args.threads,split=args.split,load_s=load,
                input='public human speech; HF viewer MP3 derivative; ' + ('48 kHz simulated microphone -> production VAD/ASR' if args.pipeline else 'whole clip'),
                summary=summary(rows),datasets={d:summary([r for r in rows if r['dataset']==d])
                    for d in sorted({r['dataset'] for r in rows})},rows=rows)
    suffix='-pipeline' if args.pipeline else ''
    if args.input != 'ME': suffix+='-'+args.input
    if args.boost_loopback: suffix+='-boost'
    if args.vad_threshold is not None: suffix+=f'-vad{args.vad_threshold}'
    if args.tag: suffix+='-'+args.tag
    path=ROOT/'logs'/f'human-{args.engine}-t{args.threads}-{args.split}{suffix}.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report['summary']),flush=True)


if __name__=='__main__': main()
