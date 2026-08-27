"""Disk partitioning via upstream tools (spec §16-§17).

Automatic UEFI layout:

    p1  EFI System Partition  (fat32, +1G, mounted at /boot)
    p2  Linux filesystem      (rest)

The ESP is mounted at /boot (not /boot/efi) because systemd-boot can
only load kernels from the ESP itself; with the ESP at /boot the
vmlinuz/initramfs images mkinitcpio writes land directly on the ESP.

All commands are generated and can be inspected before execution; execution
requires both dry_run=False and confirm=True (explicit user consent).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

EFI_SIZE_MIB = 1024
SUPPORTED_FILESYSTEMS = ("ext4", "btrfs")


@dataclass
class PartitionPlan:
    device: str
    filesystem: str = "ext4"
    efi_partition: str = "1"
    root_partition: str = "2"

    def sfdisk_script(self) -> str:
        fs_type = "btrfs" if self.filesystem == "btrfs" else "linux"
        return (
            f"label: gpt\n"
            f"unit: sectors\n"
            f"\n"
            f"name=\"EFI system partition\", size={EFI_SIZE_MIB * 2048}, "
            f"type=U\n"
            f"name=\"Linux filesystem\", type={fs_type}\n"
        )


def mkfs_command(fs: str, partition: str) -> list[str]:
    if fs == "ext4":
        return ["mkfs.ext4", "-F", partition]
    if fs == "btrfs":
        return ["mkfs.btrfs", "-f", partition]
    raise ValueError(f"unsupported filesystem: {fs}")


def mount_commands(root_partition: str, fs: str, efi_partition: str,
                   root_mount: str = "/mnt") -> list[list[str]]:
    """Build commands to mount the freshly-created partitions.

    The first argument is the *root partition* (e.g. /dev/sda2), not the
    whole device — mounting a raw device on /mnt destroys any existing
    partition table contents. The ESP is mounted at <root>/boot so both
    systemd-boot and GRUB find their kernels on the ESP (GRUB reads it
    via its fat driver, systemd-boot requires it).
    """
    if not root_partition or not efi_partition:
        raise ValueError("both root_partition and efi_partition are required")
    if root_partition == efi_partition:
        raise ValueError("root_partition and efi_partition must differ")
    return [
        ["mount", root_partition, root_mount],
        ["mkdir", "-p", f"{root_mount}/boot"],
        ["mount", efi_partition, f"{root_mount}/boot"],
    ]


def umount_all(root_mount: str = "/mnt") -> list[list[str]]:
    return [
        [shutil.which("umount") or "umount", "-R", f"{root_mount}/boot"],
        [shutil.which("umount") or "umount", "-R", root_mount],
    ]


def _size_to_gb(size_str: str | None) -> int | None:
    """Parse an lsblk size string like '500G', '1.5T' into integer GB."""
    if not size_str:
        return None
    s = size_str.strip().upper()
    if not s:
        return None
    try:
        if s.endswith("T"):
            return int(float(s[:-1]) * 1024)
        if s.endswith("G"):
            return int(float(s[:-1]))
        if s.endswith("M"):
            return int(float(s[:-1]) / 1024)
        return int(s)
    except (ValueError, IndexError):
        return None


def is_safe_install_target(device: StorageDevice,
                           min_size_gb: int = 8) -> bool:
    """True if a storage device is a valid install target.

    Filters out loopbacks (the live ISO's own device), RAM disks, optical
    drives, and anything smaller than the minimum safe install size.
    """
    name = (device.name or "").strip()
    if not name:
        return False
    lower = name.lower()
    if lower.startswith(("loop", "ram", "zram", "sr", "fd")):
        return False
    if device.removable:
        return False
    size_gb = _size_to_gb(device.size)
    if size_gb is not None and size_gb < min_size_gb:
        return False
    return True


class Partitioner:
    """Generates and (optionally) executes the automatic partitioning plan."""

    def __init__(self, device: str, filesystem: str = "ext4",
                 dry_run: bool = True):
        if filesystem not in SUPPORTED_FILESYSTEMS:
            raise ValueError(f"unsupported filesystem: {filesystem}")
        if not device.startswith("/dev/"):
            raise ValueError(f"not a block device path: {device}")
        self.device = device
        self.filesystem = filesystem
        self.dry_run = dry_run
        self.log: list[str] = []

    def plan(self) -> PartitionPlan:
        base = self.device
        if base.startswith("/dev/nvme") or base.startswith("/dev/mmcblk"):
            efi = f"{base}p1"
            root = f"{base}p2"
        else:
            efi = f"{base}1"
            root = f"{base}2"
        return PartitionPlan(device=self.device, filesystem=self.filesystem,
                             efi_partition=efi, root_partition=root)

    def commands(self) -> list[list[str]]:
        plan = self.plan()
        cmds: list[list[str]] = []
        cmds.append(["sfdisk", "--wipe", "always", self.device])
        # Give udev a moment to create the partition device nodes before
        # mkfs runs; without this, fast machines can race the kernel.
        cmds.append(["udevadm", "settle", "--timeout", "10"])
        cmds.append(mkfs_command(self.filesystem, plan.root_partition))
        cmds.append(["mkfs.fat", "-F", "32", plan.efi_partition])
        cmds.extend(mount_commands(plan.root_partition, self.filesystem,
                                   plan.efi_partition))
        return cmds

    def execute(self, confirm: bool = False) -> int:
        if self.dry_run:
            for c in self.commands():
                self.log.append("DRY-RUN: " + " ".join(c))
            return 0
        if not confirm:
            raise PermissionError(
                "refusing destructive disk operation without explicit confirmation"
            )

        commands = self.commands()
        for i, cmd in enumerate(commands):
            stdin: str | None = None
            if cmd[0] == "sfdisk":
                # sfdisk reads the partition layout description from
                # stdin; without it it blocks forever waiting for input.
                stdin = self.plan().sfdisk_script()
            proc = subprocess.run(cmd, input=stdin, capture_output=True,
                                  text=True, timeout=120)
            self.log.append(" ".join(cmd))
            if proc.returncode != 0:
                self.log.append(proc.stderr.strip())
                # Best-effort rollback: try to unmount whatever was mounted
                # and mark the disk as needing manual cleanup.
                for later in commands[i + 1:]:
                    if later and later[0] == "mount":
                        self.log.append("rollback: skipping later mount "
                                        + " ".join(later))
                self._try_umount("/mnt/boot")
                self._try_umount("/mnt")
                return proc.returncode
        return 0

    @staticmethod
    def _try_umount(target: str) -> None:
        try:
            subprocess.run(["umount", "-R", target], capture_output=True,
                           text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
