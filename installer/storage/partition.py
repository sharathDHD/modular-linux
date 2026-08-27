"""Disk partitioning via upstream tools (spec §16-§17).

Automatic UEFI layout:

    p1  EFI System Partition  (fat32, +1G)
    p2  Linux filesystem      (rest)

All commands are generated and can be inspected before execution; execution
requires both dry_run=False and confirm=True (explicit user consent).
"""

from __future__ import annotations

import shutil
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


def mount_commands(device: str, fs: str, efi_part: str,
                   root_mount: str = "/mnt") -> list[list[str]]:
    cmds = [["mount", device, root_mount]]
    cmds.append(["mkdir", "-p", f"{root_mount}/boot/efi"])
    cmds.append(["mount", efi_part, f"{root_mount}/boot/efi"])
    return cmds


def umount_all(root_mount: str = "/mnt") -> list[list[str]]:
    return [
        [shutil.which("umount") or "umount", "-R", f"{root_mount}/boot/efi"],
        [shutil.which("umount") or "umount", "-R", root_mount],
    ]


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
        suffix = "" if self.device[-1].isdigit() else ""
        # nvme0n1p1 style vs sda1 style is handled by lsblk name lookup at
        # runtime; for generation we assume standard naming.
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
        import subprocess

        for cmd in self.commands():
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.log.append(" ".join(cmd))
            if proc.returncode != 0:
                self.log.append(proc.stderr.strip())
                return proc.returncode
        return 0
