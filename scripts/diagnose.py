"""Local model/device verification. Only the bundled public test WAV is read."""
import json
from pathlib import Path
import sys
import time
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from app.config.settings import ROOT, load_settings
from app.audio.devices import enumerate_devices
from app.audio.preprocess import AudioPreprocessor
from app.asr.recognizer import Recognizer
from app.vad.detector import Detector
from download_models import MODEL_NAME


def read_wav(path):
    with wave.open(str(path), 'rb') as wav:
        assert wav.getsampwidth() == 2
        rate, channels = wav.getframerate(), wav.getnchannels()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), np.int16).astype(np.float32) / 32768
    return AudioPreprocessor(rate, channels).process(samples, final=True)


def main():
    settings = load_settings()
    report = {'python': sys.version, 'executable': sys.executable, 'devices': enumerate_devices()}
    t = time.perf_counter()
    recognizer = Recognizer(ROOT / 'models', settings['asr_threads'], engine=settings['asr_engine'])
    report['engine'] = settings['asr_engine']
    report['model_load_s'] = time.perf_counter() - t
    detector = Detector(ROOT / 'models' / 'silero_vad.onnx', settings['vad'])
    report['vad_loaded'] = True
    audio = read_wav(ROOT / 'models' / MODEL_NAME / 'test_wavs' / '1.wav')
    t = time.perf_counter()
    result = recognizer.recognize(audio)
    seconds = time.perf_counter() - t
    assert result, 'ASR returned no text'
    report.update(test_wav='1.wav', text=result, audio_s=len(audio) / 16000,
                  asr_s=seconds, RTF=seconds / (len(audio) / 16000))
    segments = []
    padded = np.concatenate((np.zeros(16000, np.float32), audio, np.zeros(16000, np.float32)))
    for i in range(0, len(padded), 512):
        segments.extend(detector.accept(padded[i:i + 512]))
    segments.extend(detector.flush())
    assert segments, 'VAD did not detect bundled speech'
    report['vad_segments'] = [{'start_s': a / 16000, 'end_s': b / 16000, 'audio_s': len(x) / 16000} for a,b,x in segments]
    (ROOT / 'logs').mkdir(exist_ok=True)
    (ROOT / 'logs' / 'diagnostic.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)


if __name__ == '__main__':
    main()
