"""Two simultaneous wall-clock audio streams -> production pipeline -> Qt display.

Uses public human evaluation audio, never a physical microphone or audio upload.
"""
import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import threading
import time
import numpy as np
import soxr
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from app.audio.microphone import MicrophoneAudioSource
from app.asr.worker import ASRWorker
from app.config.settings import load_settings
from app.pipeline import Channel
from app.records import Speaker
from app.ui.main_window import MainWindow
from scripts.benchmark_human import ROOT, DATA, audio, make_model
from scripts.benchmark_recognition import normalize, distance


class Relay(QObject):
    state=Signal(str); error=Signal(str); devices=Signal(object); result=Signal(object)
    meter=Signal(str,int,bool); busy=Signal(bool); closed=Signal(); exported=Signal(int)
    def __init__(self,*args): super().__init__()
    def command(self,*args): pass


class PacedSource(MicrophoneAudioSource):
    def __init__(self,samples,barrier):
        super().__init__()
        self.sample_rate=48000; self.channels=2
        x=soxr.resample(samples,16000,48000)
        self.samples=np.repeat(x[:,None],2,axis=1).astype(np.float32)
        self.barrier=barrier; self.done=threading.Event(); self.producer=None
    def open(self): pass
    def start(self):
        def produce():
            self.barrier.wait(timeout=15)
            started=time.monotonic()
            for i in range(0,len(self.samples),960):
                if self.closing.wait(max(0,started+i/48000-time.monotonic())): break
                x=self.samples[i:i+960]
                self._callback(x.tobytes(),len(x),{},0)
            self.done.set()
        self.producer=threading.Thread(target=produce,name='PacedPublicAudio')
        self.producer.start()
    def check(self):
        if self.error: raise self.error
    def stop(self):
        self.closing.set()
        if self.producer: self.producer.join()
    def close(self): self.stop()


def main():
    p=argparse.ArgumentParser(); p.add_argument('--engine',default='reazon')
    p.add_argument('--threads',type=int,default=2); p.add_argument('--count',type=int,default=8)
    args=p.parse_args()
    config=load_settings(); config['asr_engine']=args.engine
    config['asr_threads']=args.threads
    refs=json.loads((DATA/'references.json').read_text('utf-8'))
    refs=[r for r in refs if r['split']=='holdout']
    groups=[[r for r in refs if r['dataset']==d][:args.count] for d in sorted({r['dataset'] for r in refs})]
    tracks=[]
    for group in groups:
        parts=[np.zeros(8000,np.float32)]
        for ref in group:
            parts += [audio(ref),np.zeros(19200,np.float32)]
        parts.append(np.zeros(32000,np.float32)); tracks.append(np.concatenate(parts))
    app=QApplication([]); app.setStyle('Fusion')
    w=MainWindow(copy.deepcopy(config),ROOT,Relay); w.show()
    w.set_state('録音中'); app.processEvents()
    errors=[]; received=[]; relay=w.controller
    relay.result.disconnect(w.add_result)
    def displayed(record):
        w.add_result(record)
        w.transcript.viewport().repaint()
        rendered_latency = max(0, time.monotonic() - record.ended_monotonic)
        received.append(dict(speaker=record.speaker.value,text=record.raw_text,
            latency_s=rendered_latency,asr_s=record.asr_processing_ms/1000,
            audio_s=record.audio_duration_ms/1000))
    relay.result.connect(displayed)
    model=make_model(args.engine,args.threads)
    worker=ASRWorker(model,{},relay.result.emit,errors.append)
    barrier=threading.Barrier(2)
    sources=[PacedSource(x,barrier) for x in tracks]
    channels=[Channel(s,sp,config['vad'],ROOT/'models/silero_vad.onnx',worker,
                      relay.meter.emit,errors.append) for s,sp in zip(sources,[Speaker.ME,Speaker.OTHER])]
    worker.start(); started=time.monotonic(); cpu_started=time.process_time(); peak_queue=0
    try:
        for c in channels: c.start()
        deadline=started+max(len(t)/16000 for t in tracks)+60
        while not all(s.done.is_set() for s in sources):
            app.processEvents(); peak_queue=max(peak_queue,worker.queue.qsize())
            if time.monotonic()>deadline: raise TimeoutError('Replay did not complete')
            time.sleep(.005)
        for c in channels: c.request_stop()
        while any(c.is_alive() for c in channels) or worker.queue.unfinished_tasks:
            app.processEvents(); peak_queue=max(peak_queue,worker.queue.qsize())
            if time.monotonic()>deadline: raise TimeoutError('Pipeline did not drain')
            time.sleep(.005)
        app.processEvents()
    finally:
        for c in channels: c.request_stop()
        for c in channels: c.join()
        worker.shutdown()
    by_speaker={}
    for speaker,group in zip(['ME','OTHER'],groups):
        expected=normalize(''.join(r['text'] for r in group))
        actual=normalize(''.join(r['text'] for r in received if r['speaker']==speaker))
        by_speaker[speaker]=dict(edits=distance(expected,actual),characters=len(expected),CER=distance(expected,actual)/len(expected))
    latencies=[r['latency_s'] for r in received]
    report=dict(engine=args.engine,threads=args.threads,wall_s=time.monotonic()-started,
        process_cpu_s=time.process_time()-cpu_started,
        source='public holdout audio; simultaneous 20 ms wall-clock callbacks; actual Qt rendering',
        latency_reference='production VAD detected speech end to MainWindow.add_result and synchronous viewport repaint; includes wait, recognition and Qt rendering',
        clips=sum(map(len,groups)),peak_queue=peak_queue,errors=errors,
        latency_p50_s=float(np.percentile(latencies,50)),latency_p95_s=float(np.percentile(latencies,95)),
        latency_max_s=max(latencies),speakers=by_speaker,rows=received,
        remaining_threads=[t.name for t in threading.enumerate() if t is not threading.main_thread()])
    report['passed']=not errors and report['latency_p95_s']<=3 and peak_queue<=2 and not report['remaining_threads']
    dest=ROOT/'logs'/f'live-{args.engine}-t{args.threads}.json'
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    w.grab().save(str(ROOT/'logs'/f'live-{args.engine}.png'))
    w.can_close=True; w.close()
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
    if not report['passed']: sys.exit(1)


if __name__=='__main__': main()
