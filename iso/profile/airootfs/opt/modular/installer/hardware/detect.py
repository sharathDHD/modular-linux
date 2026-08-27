"""Hardware detection using standard Linux utilities (spec §8).

Every probe degrades gracefully: on systems without the underlying tool or
sysfs entries the corresponding field reports as unknown/absent rather than
raising.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field


def _run(cmd: list[str], timeout: int = 10) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return None


@dataclass
class CpuInfo:
    model: str | None = None
    cores: int | None = None
    vendor: str | None = None

    @property
    def present(self) -> bool:
        return self.model is not None


@dataclass
class MemoryInfo:
    total_mb: int | None = None


@dataclass
class GpuInfo:
    devices: list[str] = field(default_factory=list)

    @property
    def present(self) -> bool:
        return bool(self.devices)

    @property
    def vendors(self) -> set[str]:
        out = set()
        for dev in self.devices:
            low = dev.lower()
            if "nvidia" in low:
                out.add("nvidia")
            elif "amd" in low or "ati" in low or "radeon" in low:
                out.add("amd")
            elif "intel" in low:
                out.add("intel")
            else:
                out.add("unknown")
        return out


@dataclass
class StorageDevice:
    name: str
    size: str | None = None
    model: str | None = None
    removable: bool = False


@dataclass
class HardwareInfo:
    cpu: CpuInfo = field(default_factory=CpuInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    gpu: GpuInfo = field(default_factory=GpuInfo)
    storage: list[StorageDevice] = field(default_factory=list)
    ethernet: bool = False
    wifi: bool = False
    bluetooth: bool = False
    audio: bool = False
    webcam: bool = False
    touchpad: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def detect_cpu() -> CpuInfo:
    info = CpuInfo()
    output = _run(["lscpu"])
    if output:
        for line in output.splitlines():
            if line.startswith("Model name:"):
                info.model = line.split(":", 1)[1].strip()
            elif line.startswith("Vendor ID:"):
                info.vendor = line.split(":", 1)[1].strip()
            elif line.startswith("CPU(s):"):
                try:
                    info.cores = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        return info
    # fallback to /proc/cpuinfo
    text = _read("/proc/cpuinfo")
    if text:
        for line in text.splitlines():
            if line.startswith("model name"):
                info.model = line.split(":", 1)[1].strip()
                break
    return info


def detect_memory() -> MemoryInfo:
    output = _run(["free", "-m"])
    if not output:
        output = _read("/proc/meminfo")
        if output:
            match = re.search(r"MemTotal:\s+(\d+)\s+kB", output)
            if match:
                return MemoryInfo(total_mb=int(match.group(1)) // 1024)
        return MemoryInfo()
    lines = [l for l in output.splitlines() if l.lower().startswith("mem:")]
    if lines:
        parts = lines[0].split()
        try:
            return MemoryInfo(total_mb=int(parts[1]))
        except (IndexError, ValueError):
            return MemoryInfo()
    return MemoryInfo()


def detect_gpu() -> GpuInfo:
    info = GpuInfo()
    output = _run(["lspci"])
    if output is None:
        # fallback: scan /sys/class/drm card devices
        try:
            cards = sorted(os.listdir("/sys/class/drm"))
            info.devices = [c for c in cards if re.fullmatch(r"card\d+", c)]
        except OSError:
            pass
        return info
    for line in output.splitlines():
        if "VGA compatible controller" in line or "3D controller" in line \
                or "Display controller" in line:
            info.devices.append(line.strip())
    return info


def detect_storage() -> list[StorageDevice]:
    devices: list[StorageDevice] = []
    output = _run(["lsblk", "-dno", "NAME,SIZE,MODEL,RM"])
    if output:
        for line in output.splitlines()[1:]:
            parts = [p.strip() for p in line.split("|")] if "|" in line else line.split(None, 3)
            if len(parts) < 1:
                continue
            name = parts[0]
            size = parts[1] if len(parts) > 1 and parts[1] else None
            model = parts[2] if len(parts) > 2 and parts[2] else None
            removable = bool(parts[3].strip() == "1") if len(parts) > 3 and parts[3].strip() else False
            devices.append(StorageDevice(name=name, size=size, model=model,
                                         removable=removable))
        return devices
    try:
        for entry in sorted(os.listdir("/sys/block")):
            if entry.startswith(("loop", "ram", "zram")):
                continue
            size_sectors = _read(f"/sys/block/{entry}/size")
            size = None
            if size_sectors:
                size = f"{int(size_sectors) * 512 // (1024 ** 3)}G"
            devices.append(StorageDevice(name=entry, size=size))
    except OSError:
        pass
    return devices


def detect_ethernet() -> bool:
    try:
        for iface in os.listdir("/sys/class/net"):
            if iface == "lo":
                continue
            device = os.path.realpath(f"/sys/class/net/{iface}/device")
            class_path = os.path.join(device, "class")
            cls = _read(class_path)
            # PCI class 02 = network controller; distinguish from wireless via wireless dir
            if os.path.isdir(f"/sys/class/net/{iface}/wireless"):
                continue
            if cls is None or True:
                # presence of a wired interface without wireless dir
                if not os.path.isdir(f"/proc/sys/net/ipv4/conf/{iface}"):
                    continue
                return True
    except OSError:
        pass
    return False


def detect_wifi() -> bool:
    try:
        for iface in os.listdir("/sys/class/net"):
            if os.path.isdir(f"/sys/class/net/{iface}/wireless") or \
                    os.path.isdir(f"/sys/class/net/{iface}/phy80211"):
                return True
    except OSError:
        pass
    output = _run(["rfkill", "list"])
    if output and "Wireless LAN" in output:
        return True
    return False


def detect_bluetooth() -> bool:
    output = _run(["rfkill", "list"])
    if output and "Bluetooth" in output:
        return True
    try:
        for entry in os.listdir("/sys/class/bluetooth"):
            if entry.startswith("hci"):
                return True
    except OSError:
        pass
    return False


def detect_audio() -> bool:
    if os.path.isdir("/proc/asound"):
        try:
            cards = os.listdir("/proc/asound")
            return any(c.startswith("card") for c in cards)
        except OSError:
            return False
    return False


def detect_webcam() -> bool:
    try:
        for entry in os.listdir("/sys/class/video4linux"):
            return True
    except OSError:
        pass
    output = _run(["lsusb"])
    if output and re.search(r"(?i)webcam|camera|video", output):
        return True
    return False


def detect_touchpad() -> bool:
    output = _run(["udevadm", "info", "--export-db"], timeout=15)
    if output:
        section = False
        for line in output.splitlines():
            if line.startswith("P:") :
                section = False
            if "ID_INPUT_TOUCHPAD=1" in line:
                return True
        return False
    try:
        for path in ("/proc/bus/input/devices",):
            text = _read(path)
            if text and re.search(r"(?i)touchpad", text):
                return True
    except OSError:
        pass
    return False


def detect() -> HardwareInfo:
    """Run all detection probes and aggregate results."""
    native = detect_via_native_binary()
    if native is not None:
        return native
    return HardwareInfo(
        cpu=detect_cpu(),
        memory=detect_memory(),
        gpu=detect_gpu(),
        storage=detect_storage(),
        ethernet=detect_ethernet(),
        wifi=detect_wifi(),
        bluetooth=detect_bluetooth(),
        audio=detect_audio(),
        webcam=detect_webcam(),
        touchpad=detect_touchpad(),
    )


def _native_binary_path() -> str | None:
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "bin", "modular-detect"),
        "/usr/bin/modular-detect",
        "/usr/local/bin/modular-detect",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def detect_via_native_binary() -> HardwareInfo | None:
    """Prefer the zero-dependency C prober when it is available.

    The live ISO ships bin/modular-detect so hardware detection works even
    when lscpu/rfkill/lsblk are not present in the minimal environment.
    """
    import json

    binary = _native_binary_path()
    if binary is None:
        return None
    output = _run([binary])
    if not output:
        return None
    try:
        data = json.loads(output)
    except ValueError:
        return None

    cpu = CpuInfo(
        model=data.get("cpu", {}).get("model"),
        cores=data.get("cpu", {}).get("cores"),
        vendor=data.get("cpu", {}).get("vendor"),
    )
    memory = MemoryInfo(total_mb=data.get("memory", {}).get("total_mb"))
    gpu = GpuInfo(devices=[
        f"{g['id']} ({g['vendor']})" for g in data.get("gpu", [])
        if isinstance(g, dict)
    ])
    storage = [
        StorageDevice(name=s.get("name", ""),
                      size=f"{s.get('size_gb', 0)}G" if s.get("size_gb") else None,
                      model=s.get("model") or None)
        for s in data.get("storage", []) if isinstance(s, dict)
    ]
    network = data.get("network", {})
    return HardwareInfo(
        cpu=cpu,
        memory=memory,
        gpu=gpu,
        storage=storage,
        ethernet=bool(network.get("ethernet")),
        wifi=bool(network.get("wifi")),
        bluetooth=bool(data.get("bluetooth")),
        audio=bool(data.get("audio")),
        webcam=bool(data.get("webcam")),
        touchpad=bool(data.get("touchpad")),
    )
