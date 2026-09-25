import pyaudiowpatch as pa


def enumerate_devices():
    with pa.PyAudio() as p:
        devices = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
        wasapi = p.get_host_api_info_by_type(pa.paWASAPI)['index']
        all_microphones = [d for d in devices if d['maxInputChannels'] > 0 and not d.get('isLoopbackDevice', False)]
        microphones = [d for d in all_microphones if d['hostApi'] == wasapi] or all_microphones
        outputs = [d for d in devices if d['hostApi'] == wasapi and d['maxOutputChannels'] > 0]
        loopbacks = list(p.get_loopback_device_info_generator())
        return {'microphones': microphones, 'outputs': outputs, 'loopbacks': loopbacks,
                'all_microphones': all_microphones}
