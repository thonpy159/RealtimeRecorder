"""Play the public model test WAV locally and recognize the actual WASAPI mix."""
import json
from pathlib import Path
import sys
import time
import threading
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pyaudiowpatch as pa
import soxr
from app.config.settings import ROOT, load_settings
from app.audio.loopback import LoopbackAudioSource
from app.asr.recognizer import Recognizer
from app.asr.worker import ASRWorker
from app.pipeline import Channel
from app.records import Speaker
from app.utils.logging import configure_logging
from scripts.diagnose import read_wav
from download_models import MODEL_NAME


def main():
    configure_logging(ROOT / 'logs')
    config = load_settings()
    results, errors = [], []
    model = Recognizer(ROOT / 'models', 2)
    worker = ASRWorker(model, config['dictionary'], results.append, errors.append)
    worker.start()
    channel = Channel(LoopbackAudioSource(), Speaker.OTHER, config['vad'], ROOT / 'models' / 'silero_vad.onnx',
                      worker, lambda *args: None, errors.append)
    channel.start()
    try:
        assert channel.ready.wait(15) and not channel.start_error
        audio = read_wav(ROOT / 'models' / MODEL_NAME / 'test_wavs' / '2.wav')
        with pa.PyAudio() as p:
            output = p.get_default_wasapi_device(d_out=True)
            rate, channels = int(output['defaultSampleRate']), int(output['maxOutputChannels'])
            data = soxr.resample(audio, 16000, rate)
            data = np.repeat((data * .5)[:, None], channels, axis=1).astype(np.float32)
            stream = p.open(format=pa.paFloat32, channels=channels, rate=rate,
                            output=True, output_device_index=int(output['index']))
            try:
                stream.write(data.tobytes())
            finally:
                stream.close()
        deadline = time.monotonic() + 10
        minimum_wait = time.monotonic() + 2
        while (not results or time.monotonic() < minimum_wait) and not errors and time.monotonic() < deadline:
            time.sleep(.1)
    finally:
        channel.request_stop()
        channel.join()
        worker.shutdown()
    report = {'errors': errors, 'frames': channel.frames, 'rms_peak': channel.peak,
              'results': [{'speaker': r.speaker.value, 'text_length': len(r.raw_text),
                           'audio_duration_ms': r.audio_duration_ms, 'asr_processing_ms': r.asr_processing_ms,
                           'RTF': r.asr_processing_ms / r.audio_duration_ms, 'total_latency_ms': r.total_latency_ms}
                          for r in results],
              'remaining_threads': [t.name for t in threading.enumerate() if t.name != 'MainThread']}
    report['passed'] = bool(results) and not errors and not report['remaining_threads']
    (ROOT / 'logs' / 'loopback-e2e.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(report, ensure_ascii=True), flush=True)
    assert report['passed'], 'Loopback E2E failed'


if __name__ == '__main__':
    main()
