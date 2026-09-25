import sherpa_onnx
from download_models import FILES, MODEL_NAME, validate_models


class ReazonRecognizer:
    def __init__(self, root, threads=2):
        validate_models(root)
        p = root / MODEL_NAME
        self.model = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=str(p / FILES[0]), encoder=str(p / FILES[1]),
            decoder=str(p / FILES[2]), joiner=str(p / FILES[3]),
            num_threads=threads, sample_rate=16000, feature_dim=80,
            decoding_method='greedy_search', provider='cpu', model_type='transducer')

    def recognize(self, audio):
        from app.audio.quality import stationary_broadband_noise
        if stationary_broadband_noise(audio):
            return ''
        stream = self.model.create_stream()
        stream.accept_waveform(16000, audio)
        self.model.decode_stream(stream)
        return stream.result.text.strip()


class Recognizer:
    """One selected local CPU INT8 model; never upload audio."""
    def __init__(self, root, threads=2, engine='reazon'):
        self.engine = engine
        if engine == 'reazon':
            self.model = ReazonRecognizer(root, threads)
            return
        if engine == 'sensevoice':
            from download_sensevoice import validate
            p = validate(root)
            self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(p / 'model.int8.onnx'), tokens=str(p / 'tokens.txt'),
                num_threads=threads, provider='cpu', language='ja', use_itn=True)
            return
        import os
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        from faster_whisper import WhisperModel
        from download_accuracy_model import validate
        folder = validate(root, engine)
        self.model = WhisperModel(str(folder), device='cpu', compute_type='int8',
                                  cpu_threads=threads, num_workers=1, local_files_only=True)

    def recognize(self, audio):
        import numpy as np
        # A bounded utterance gain avoids throwing away quiet speech without
        # boosting silence/noise into invented words. The VAD has already run.
        audio = np.asarray(audio, dtype=np.float32)
        rms = float(np.sqrt(np.mean(audio * audio))) if len(audio) else 0
        if rms < 1e-5:
            return ''
        if self.engine == 'reazon':
            return self.model.recognize(audio)
        gain = min(12.0, max(1.0, .06 / rms), .95 / max(float(np.max(np.abs(audio))), 1e-6))
        audio = np.ascontiguousarray(audio * gain, dtype=np.float32)
        if self.engine == 'sensevoice':
            stream = self.model.create_stream()
            stream.accept_waveform(16000, audio)
            self.model.decode_stream(stream)
            return stream.result.text.strip()
        segments, _ = self.model.transcribe(audio, language='ja', task='transcribe',
            beam_size=5, temperature=0.0, condition_on_previous_text=False,
            vad_filter=False, without_timestamps=True,
            hallucination_silence_threshold=None)
        return ''.join(segment.text for segment in segments).strip()
