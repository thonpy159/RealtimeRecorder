import logging
import os
import threading
from copy import deepcopy
from PySide6.QtCore import QObject, Signal
from app.asr.recognizer import Recognizer
from app.asr.worker import ASRWorker
from app.audio.devices import enumerate_devices
from app.audio.microphone import MicrophoneAudioSource
from app.audio.loopback import LoopbackAudioSource
from app.pipeline import Channel
from app.records import Speaker

log = logging.getLogger(__name__)


class Controller(QObject):
    state = Signal(str)
    error = Signal(str)
    devices = Signal(object)
    result = Signal(object)
    meter = Signal(str, int, bool)
    busy = Signal(bool)
    closed = Signal()
    exported = Signal(int)

    def __init__(self, settings, root):
        super().__init__()
        self.settings, self.root = deepcopy(settings), root
        self.commands = __import__('queue').Queue()
        self.worker = None
        self.channels = []
        self.thread = threading.Thread(target=self._run, name='Controller', daemon=False)
        self.thread.start()

    def command(self, name, payload=None):
        self.commands.put((name, payload))

    def _failure(self, message):
        self.error.emit(message)
        self.command('stop')

    def _stop(self):
        self.state.emit('停止処理中')
        for channel in self.channels:
            channel.request_stop()
        for channel in self.channels:
            channel.join()
        self.channels.clear()
        if self.worker:
            self.worker.drain()
        self.state.emit('停止中' if self.worker else 'エラー')

    def _prepare(self):
        self.state.emit('準備中')
        self.devices.emit(enumerate_devices())
        if self.worker is None:
            recognizer = Recognizer(self.root / 'models', self.settings['asr_threads'],
                                    engine=self.settings.get('asr_engine', 'reazon'))
            self.worker = ASRWorker(recognizer, self.settings['dictionary'], self.result.emit,
                                    self.error.emit, self.busy.emit, self.settings['asr_queue_size'])
            self.worker.start()
        self.state.emit('準備完了')

    def _run(self):
        while True:
            command, payload = self.commands.get()
            try:
                if command == 'prepare':
                    self._prepare()
                elif command == 'refresh':
                    if not self.channels:
                        self.devices.emit(enumerate_devices())
                        if not self.worker:
                            self._prepare()
                        else:
                            self.state.emit('準備完了')
                elif command in ('start', 'test_mic'):
                    if self.channels:
                        continue
                    if not self.worker:
                        self._prepare()
                    self.state.emit('準備中')
                    inputs = [(MicrophoneAudioSource(payload[0]), Speaker.ME)]
                    if command == 'start':
                        inputs.append((LoopbackAudioSource(payload[1]), Speaker.OTHER))
                    for source, speaker in inputs:
                        channel = Channel(source, speaker, self.settings['vad'], self.root / 'models' / 'silero_vad.onnx',
                                          self.worker, self.meter.emit, self._failure)
                        self.channels.append(channel)
                        channel.start()
                        channel.ready.wait()
                        if channel.start_error:
                            raise RuntimeError(channel.start_error)
                    self.state.emit('録音中')
                elif command == 'stop':
                    self._stop()
                elif command == 'export':
                    try:
                        path, content, count = payload
                        temporary = path.with_name(path.name + '.tmp')
                        temporary.write_text(content, encoding='utf-8')
                        os.replace(temporary, path)
                        self.exported.emit(count)
                    except OSError:
                        log.exception('Markdown save failed')
                        self.error.emit('Markdownを保存できませんでした。保存先の権限・空き容量を確認してください。')
                elif command == 'close':
                    self._stop()
                    if self.worker:
                        self.worker.shutdown()
                        self.worker = None
                    self.closed.emit()
                    return
            except Exception as e:
                log.exception('Controller command failed: %s', command)
                self._stop()
                self.error.emit(str(e))
                self.state.emit('エラー')
            finally:
                self.commands.task_done()
