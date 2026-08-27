import pytest

from installer.storage.partition import (
    EFI_SIZE_MIB, PartitionPlan, Partitioner, mkfs_command, mount_commands,
    is_safe_install_target,
)


def test_plan_nvme_naming():
    plan = Partitioner("/dev/nvme0n1").plan()
    assert plan.efi_partition == "/dev/nvme0n1p1"
    assert plan.root_partition == "/dev/nvme0n1p2"


def test_plan_sata_naming():
    plan = Partitioner("/dev/sda").plan()
    assert plan.efi_partition == "/dev/sda1"
    assert plan.root_partition == "/dev/sda2"


def test_sfdisk_script_layout():
    script = Partitioner("/dev/sda").plan().sfdisk_script()
    assert "label: gpt" in script
    assert "type=U" in script  # EFI System Partition type
    sectors = EFI_SIZE_MIB * 2048
    assert f"size={sectors}" in script


def test_commands_sequence():
    cmds = Partitioner("/dev/vda", "ext4").commands()
    flat = [" ".join(c) for c in cmds]
    assert any(c.startswith("sfdisk") for c in flat)
    assert any(c.startswith("udevadm settle") for c in flat)
    assert "mkfs.ext4 -F /dev/vda2" in flat
    assert "mkfs.fat -F 32 /dev/vda1" in flat
    assert "mount /dev/vda2 /mnt" in flat


def test_esp_mounted_at_boot():
    # systemd-boot can only load kernels from the ESP, so the ESP must
    # be mounted at /mnt/boot (not /boot/efi).
    cmds = Partitioner("/dev/vda", "ext4").commands()
    flat = [" ".join(c) for c in cmds]
    assert "mkdir -p /mnt/boot" in flat
    assert "mount /dev/vda1 /mnt/boot" in flat
    assert not any("/boot/efi" in c for c in flat)


def test_execute_feeds_sfdisk_script(monkeypatch):
    """sfdisk must receive the partition script on stdin.

    Regression test: execute() used to run sfdisk with no stdin, which
    made it block forever waiting for interactive input.
    """
    import installer.storage.partition as partition_mod

    captured = {}

    class FakeProc:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, input=None, capture_output=True, text=True,
                 timeout=None):
        captured[cmd[0]] = input
        return FakeProc()

    monkeypatch.setattr(partition_mod.subprocess, "run", fake_run)
    p = Partitioner("/dev/vda", "ext4", dry_run=False)
    assert p.execute(confirm=True) == 0
    assert captured["sfdisk"] is not None
    assert "label: gpt" in captured["sfdisk"]
    assert "type=U" in captured["sfdisk"]
    # Non-sfdisk commands get no script stdin.
    assert captured.get("mkfs.ext4") is None


def test_dry_run_does_not_execute():
    p = Partitioner("/dev/loop99", dry_run=True)
    rc = p.execute()
    assert rc == 0
    assert all(entry.startswith("DRY-RUN:") for entry in p.log)


def test_refuses_without_confirmation():
    p = Partitioner("/dev/loop99", dry_run=False)
    with pytest.raises(PermissionError):
        p.execute(confirm=False)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        Partitioner("sda")
    with pytest.raises(ValueError):
        Partitioner("/dev/sda", filesystem="ntfs")


def test_mkfs_btrfs():
    assert mkfs_command("btrfs", "/dev/x") == ["mkfs.btrfs", "-f", "/dev/x"]
    with pytest.raises(ValueError):
        mkfs_command("f2fs", "/dev/x")


def test_mount_order():
    cmds = mount_commands("/dev/vda2", "ext4", "/dev/vda1", root_mount="/mnt")
    assert cmds[0] == ["mount", "/dev/vda2", "/mnt"]
    assert cmds[2] == ["mount", "/dev/vda1", "/mnt/boot"]


def test_mount_rejects_same_partition():
    import pytest
    with pytest.raises(ValueError):
        mount_commands("/dev/vda1", "ext4", "/dev/vda1")


def test_mount_rejects_empty_args():
    import pytest
    with pytest.raises(ValueError):
        mount_commands("", "ext4", "/dev/vda1")
    with pytest.raises(ValueError):
        mount_commands("/dev/vda2", "ext4", "")


def test_safe_install_target_filters():
    from installer.hardware.detect import StorageDevice
    assert is_safe_install_target(StorageDevice(name="sda", size="500G"))
    assert is_safe_install_target(StorageDevice(name="nvme0n1", size="1T"))
    assert not is_safe_install_target(
        StorageDevice(name="loop0", size="2G"))  # live ISO loopback
    assert not is_safe_install_target(
        StorageDevice(name="sr0", size="700M"))  # optical
    assert not is_safe_install_target(
        StorageDevice(name="sdc", size="4G"))  # too small
    assert not is_safe_install_target(StorageDevice(name="", size="100G"))
    assert not is_safe_install_target(
        StorageDevice(name="sdc", size=None, removable=True))  # USB stick
