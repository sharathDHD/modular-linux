"""Integration-style tests for run_installation() with a mocked executor.

These tests exist specifically to cover the execution layer that the
planning-focused tests do not: every command launched, its stdin payload,
and the overall sequence. They are the regression net for the class of
bugs found in v0.2.0 (sfdisk left without its script, chpasswd never
receiving passwords, genfstab run inside the chroot, a bootloader with no
entries).

The disk-pacstrap-chroot sequence is still exercised for real in the live
ISO under QEMU (scripts/test-vm.sh); here we only verify the exact
commands the orchestrator would run.
"""
from dataclasses import dataclass, field

import pytest

import installer.installation.orchestrator as orch
from engine.configuration import ModularConfiguration
from installer.storage.partition import Partitioner


MINIMAL_CONFIG = """
version: 1
base: {distribution: arch}
system: {architecture: x86_64, kernel: linux, init: systemd}
desktop: {environment: none}
hardware: {network: true, gpu: manual}
roles: []
applications: []
shell: {type: bash}
filesystem: {type: ext4}
bootloader: {type: systemd-boot}
sources: {arch: true, aur: false, flatpak: false, appimage: false}
"""


@dataclass
class FakeCpu:
    model: str = "Fake CPU"
    cores: int = 4
    vendor: str = "GenuineIntel"


@dataclass
class FakeGpu:
    devices: list = field(default_factory=list)
    vendors: list = field(default_factory=list)


@dataclass
class FakeHardware:
    cpu: FakeCpu = field(default_factory=FakeCpu)
    gpu: FakeGpu = field(default_factory=FakeGpu)
    storage: list = field(default_factory=list)


@pytest.fixture
def captured():
    """Mock execute_step/Partitioner.execute/detect; record every command."""
    record = []

    def fake_execute_step(cmd, stdin_text=None, timeout=None):
        record.append((list(cmd), stdin_text))
        if cmd and cmd[0] == "blkid":
            return 0, "abcd-1234-uuid"
        return 0, ""

    def fake_partition_execute(self, confirm=False):
        return 0

    def fake_detect():
        return FakeHardware()

    def fake_chroot_ready(root="/mnt"):
        return True

    return (record, fake_execute_step, fake_partition_execute,
            fake_detect, fake_chroot_ready)


def _install(monkeypatch, captured, cfg_kwargs=None):
    (record, fake_step, fake_part, fake_detect,
     fake_ready) = captured
    monkeypatch.setattr(orch, "execute_step", fake_step)
    monkeypatch.setattr(Partitioner, "execute", fake_part)
    monkeypatch.setattr(orch, "detect", fake_detect)
    monkeypatch.setattr(orch, "is_chroot_ready", fake_ready)
    import yaml as yaml_mod
    data = yaml_mod.safe_load(MINIMAL_CONFIG)
    if cfg_kwargs:
        data.update(cfg_kwargs)
    cfg = ModularConfiguration.from_dict(data)
    rc = orch.run_installation(
        cfg, device="/dev/sda", username="alice", full_name="Alice A",
        user_password="userpw", root_password="rootpw",
        opts=orch.InstallOptions(extra_services=["bluetooth"]))
    return rc, record


def test_installation_completes(monkeypatch, captured):
    rc, record = _install(monkeypatch, captured)
    assert rc == 0


def test_genfstab_runs_outside_chroot(monkeypatch, captured):
    """Regression: genfstab was run *inside* the chroot, so '>> /mnt/etc/fstab'
    resolved to /mnt/mnt/etc/fstab and the step failed."""
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    genfstab = [(c, s) for c, s in record if c[:1] == ["bash"]
                and "genfstab" in " ".join(c)]
    assert genfstab, "genfstab must run via bash -c from the live env"
    cmd, _ = genfstab[0]
    assert "genfstab -U /mnt" in cmd[2]
    # ... and never through arch-chroot:
    chrooted = [c for c, _ in record
                if c[:1] == ["arch-chroot"] and "genfstab" in " ".join(c)]
    assert not chrooted


def test_chpasswd_receives_passwords_on_stdin(monkeypatch, captured):
    """Regression: cmd[-2:] == ['chpasswd'] never matched
    ['arch-chroot','/mnt','chpasswd'], so passwords never reached
    chpasswd and user setup failed."""
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    chpasswd = [(c, s) for c, s in record if c[-1:] == ["chpasswd"]]
    assert len(chpasswd) == 2, "user + root chpasswd calls expected"
    assert chpasswd[0][1] == "alice:userpw\n"
    assert chpasswd[1][1] == "root:rootpw\n"
    # Passwords must never appear in any argv.
    for cmd, _ in record:
        assert "userpw" not in cmd and "rootpw" not in cmd


def test_pacstrap_includes_microcode(monkeypatch, captured):
    """CPU vendor is GenuineIntel -> intel-ucode must be installed."""
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    pacstrap = [c for c, _ in record if c[:1] == ["pacstrap"]]
    assert pacstrap
    assert "intel-ucode" in pacstrap[0]


def test_systemd_boot_gets_loader_entries(monkeypatch, captured):
    """Regression: bootctl install alone leaves the system unbootable;
    loader.conf + entries with the root PARTUUID must be written."""
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    assert any(c[:2] == ["arch-chroot", "/mnt"] and "bootctl" in c
               for c, _ in record)
    written = {tuple(cmd) if isinstance(cmd, list) else cmd: stdin
               for cmd, stdin in record
               if cmd[:1] == ["tee"]}
    assert "/mnt/boot/loader/loader.conf" in [c[-1] for c, _ in record
                                              if c[:1] == ["tee"]]
    entry_writes = [(c, s) for c, s in record
                    if c[:1] == ["tee"] and "arch.conf" in " ".join(c)]
    assert entry_writes
    content = entry_writes[0][1]
    assert "root=PARTUUID=abcd-1234-uuid" in content
    assert "intel-ucode.img" in content
    assert "/mnt/boot/loader/entries/arch-fallback.conf" in \
        [c[-1] for c, _ in record if c[:1] == ["tee"]]


def test_grub_adds_packages_and_uses_boot(monkeypatch, captured):
    rc, record = _install(monkeypatch, captured,
                          cfg_kwargs={"bootloader": {"type": "grub"}})
    assert rc == 0
    pacstrap = [c for c, _ in record if c[:1] == ["pacstrap"]]
    assert "grub" in pacstrap[0] and "efibootmgr" in pacstrap[0]
    grub_install = [c for c, _ in record if "grub-install" in " ".join(c)]
    assert grub_install
    assert "--efi-directory=/boot" in grub_install[0]
    # No systemd-boot loader entries on the grub path.
    assert not [c for c, _ in record
                if c[:1] == ["tee"] and "loader" in " ".join(c)]


def test_btrfs_adds_btrfs_progs(monkeypatch, captured):
    rc, record = _install(monkeypatch, captured,
                          cfg_kwargs={"filesystem": {"type": "btrfs"}})
    assert rc == 0
    pacstrap = [c for c, _ in record if c[:1] == ["pacstrap"]]
    assert "btrfs-progs" in pacstrap[0]


def test_extra_services_enabled(monkeypatch, captured):
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    enabled = [" ".join(c) for c, _ in record
               if c[:1] == ["systemctl"] and "enable" in c]
    assert any("bluetooth.service" in e for e in enabled)


def test_exports_modular_yaml(monkeypatch, captured):
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    export = [(c, s) for c, s in record
              if c[:1] == ["tee"] and "etc/modular" in " ".join(c)]
    assert export
    assert "version" in export[0][1]


def test_unmounts_on_success(monkeypatch, captured):
    rc, record = _install(monkeypatch, captured)
    assert rc == 0
    umounts = [" ".join(c) for c, _ in record if c[:1] == ["umount"]]
    assert any("/mnt/boot" in u for u in umounts)
    assert any(u.endswith("/mnt") for u in umounts)


def test_failure_unmounts_best_effort(monkeypatch, captured):
    record, fake_step, fake_part, fake_detect, fake_ready = captured

    def failing_step(cmd, stdin_text=None, timeout=None):
        record.append((list(cmd), stdin_text))
        if cmd[:1] == ["pacstrap"]:
            return 1, "mock pacstrap failure"
        return 0, ""

    monkeypatch.setattr(orch, "execute_step", failing_step)
    monkeypatch.setattr(Partitioner, "execute", fake_part)
    monkeypatch.setattr(orch, "detect", fake_detect)
    monkeypatch.setattr(orch, "is_chroot_ready", fake_ready)
    import yaml as yaml_mod
    cfg = ModularConfiguration.from_dict(yaml_mod.safe_load(MINIMAL_CONFIG))
    rc = orch.run_installation(cfg, device="/dev/sda", username="alice",
                               full_name="Alice A", user_password="pw")
    assert rc == 1
    umounts = [" ".join(c) for c, _ in record if c[:1] == ["umount"]]
    assert any("/mnt/boot" in u for u in umounts)


def test_device_safety_check_enforced(monkeypatch):
    """Regression: the safety check result used to be discarded (pass)."""
    @dataclass
    class TinyDisk:
        name: str = "sda"
        size: str = "2G"      # below the 8 GB minimum
        removable: bool = False

    @dataclass
    class Hw:
        cpu = FakeCpu()
        gpu = FakeGpu()
        storage = [TinyDisk()]

    monkeypatch.setattr(orch, "detect", lambda: Hw())
    with pytest.raises(ValueError):
        orch._resolve_target_device("/dev/sda")
