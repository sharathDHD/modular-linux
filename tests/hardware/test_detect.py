from installer.hardware.detect import (
    detect_audio, detect_bluetooth, detect_cpu, detect_ethernet,
    detect_gpu, detect_memory, detect_storage, detect_touchpad,
    detect_webcam, detect_wifi,
)


def test_all_probes_run_without_exception():
    # These run against the real host; they must never raise even when
    # tools like lscpu/rfkill are unavailable.
    detect_cpu()
    detect_memory()
    detect_gpu()
    detect_storage()
    detect_ethernet()
    detect_wifi()
    detect_bluetooth()
    detect_audio()
    detect_webcam()
    detect_touchpad()


def test_cpu_detected_on_host():
    info = detect_cpu()
    assert isinstance(info.model, str) or info.model is None


def test_memory_nonnegative():
    mem = detect_memory()
    assert mem.total_mb is None or mem.total_mb >= 0


def test_storage_names_valid():
    devices = detect_storage()
    for dev in devices:
        assert dev.name
