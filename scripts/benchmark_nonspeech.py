"""Negative controls through actual VAD and ASR, not assertions about arbitrary noise."""
import json
from pathlib import Path
import sys
import wave
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.benchmark_human import ROOT, make_model
from scripts.benchmark_recognition import evaluate
from app.records import Speaker


def main():
    dest=ROOT/'models/evaluation-controls'; dest.mkdir(exist_ok=True)
    rng=np.random.default_rng(20260924); n=16000*10; t=np.arange(n)/16000
    noise=rng.normal(size=n).astype(np.float32)
    clicks=np.zeros(n,np.float32)
    for i in range(1000,n-100,8000): clicks[i:i+80]=rng.normal(0,.08,80)
    signals={'silence':np.zeros(n,np.float32),'quiet_white_noise':noise*.003,
        'loud_white_noise':noise*.03,'hum':(.02*np.sin(2*np.pi*60*t)).astype(np.float32),
        'clicks':clicks}
    refs=[]
    for name,x in signals.items():
        path=dest/(name+'.wav')
        with wave.open(str(path),'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes((np.clip(x,-1,1)*32767).astype('<i2').tobytes())
        refs.append(dict(file=str(path),text=''))
    model=make_model('reazon',2); report={}
    for threshold in [.35,.15]:
        for speaker in [Speaker.ME,Speaker.OTHER]:
            rows=evaluate(model,refs,speaker=speaker,vad_overrides={'threshold':threshold})
            report[f'{speaker.value}-{threshold}']=rows
    production_passed=all(not row['actual'] and not row['errors'] for key,rows in report.items() if key.endswith('-0.35') for row in rows)
    candidate_passed=all(not row['actual'] and not row['errors'] for key,rows in report.items() if key.endswith('-0.15') for row in rows)
    report['passed']=production_passed
    report['rejected_candidate_passed']=candidate_passed
    (ROOT/'logs/nonspeech-controls.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('Non-speech controls passed:',report['passed'],flush=True)
    if not report['passed']: sys.exit(1)


if __name__=='__main__': main()
