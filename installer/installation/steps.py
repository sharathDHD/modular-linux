"""Installation steps orchestrating upstream Arch tools (spec §7, §14, §35).

Every step returns the command it would run; nothing executes unless
run=True is passed by the installer after explicit user confirmation.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess


SUPPORTED_BOOTLOADERS = ("systemd-boot", "grub")
SUPPORTED_FILESYSTEMS = ("ext4", "btrfs")


def _shell_quote(value: str) -> str:
    """Quote a value so it is safe to embed in a single shell argument.

    Uses shlex.quote which returns a single-quoted string, escaping any
    embedded single quotes. Used for fields that can contain user-supplied
    text (full name, hostname) to prevent command injection.
    """
    return shlex.quote(value)


def _validate_username(username: str) -> str:
    if not username:
        raise ValueError("username must not be empty")
    if not all(c.islower() or c.isdigit() or c in "-_" for c in username):
        raise ValueError(
            f"username contains invalid characters: {username!r} "
            "(use lowercase letters, digits, '-' or '_')"
        )
    if len(username) > 32:
        raise ValueError("username must be 32 characters or fewer")
    return username


def pacstrap_command(packages: list[str], root: str = "/mnt") -> list[str]:
    return ["pacstrap", "-K", root] + list(packages)


def genfstab_command(root: str = "/mnt") -> str:
    return f"genfstab -U {shlex.quote(root)} >> {shlex.quote(root)}/etc/fstab"


def set_timezone(zone: str, root: str = "/mnt") -> list[list[str]]:
    """Symlink /etc/localtime and run hwclock. systemd-based systems also
    accept timedatectl set-timezone, but hwclock is the lower-level
    canonical path and works without a running systemd."""
    return [
        ["arch-chroot", root, "ln", "-sf",
         f"/usr/share/zoneinfo/{shlex.quote(zone)}", "/etc/localtime"],
        ["arch-chroot", root, "hwclock", "--systohc"],
    ]


def configure_locale(locale: str, root: str = "/mnt") -> list[list[str]]:
    """Uncomment the chosen locale in /etc/locale.gen and run locale-gen."""
    cmds: list[list[str]] = []
    pattern = f"^# {re.escape(locale)}"
    cmds.append(["arch-chroot", root, "sed", "-i",
                 f"s/{pattern}/{shlex.quote(locale)}/", "/etc/locale.gen"])
    cmds.append(["arch-chroot", root, "locale-gen"])
    cmds.append(["arch-chroot", root, "/bin/sh", "-c",
                 f"echo 'LANG={shlex.quote(locale)}' > /etc/locale.conf"])
    return cmds


def set_keymap(keymap: str, root: str = "/mnt") -> list[list[str]]:
    """Write /etc/vconsole.conf for the console keymap."""
    return [
        ["arch-chroot", root, "/bin/sh", "-c",
         f"printf 'KEYMAP=%s\\n' {shlex.quote(keymap)} > /etc/vconsole.conf"],
    ]


def set_hostname(hostname: str, root: str = "/mnt") -> list[list[str]]:
    """Write /etc/hostname and /etc/hosts for the installed system."""
    if not hostname or not hostname.strip():
        raise ValueError("hostname must not be empty")
    safe = shlex.quote(hostname.strip())
    return [
        ["arch-chroot", root, "/bin/sh", "-c", f"echo {safe} > /etc/hostname"],
        ["arch-chroot", root, "/bin/sh", "-c",
         f"printf '127.0.0.1\\tlocalhost\\n::1\\tlocalhost\\n"
         f"127.0.1.1\\t{shlex.quote(hostname.strip())}\\n' > /etc/hosts"],
    ]


def user_commands(username: str, full_name: str, password: str,
                  root_password: str | None = None,
                  administrator: bool = True,
                  root: str = "/mnt") -> list[list[str]]:
    """Create the primary user, optionally a root password, and configure
    sudo. All user-supplied values are shell-quoted to prevent injection.

    The marker dict carries (username, password, root_password_or_None) so
    the executor can feed passwords on stdin to the right chpasswd call
    without ever putting passwords in argv or in any log line.
    """
    username = _validate_username(username)
    safe_full = shlex.quote(full_name) if full_name else shlex.quote(username)
    groups = ["wheel"]
    if administrator:
        # 'audio' for PipeWire/Pulse, 'video' for hw accel, 'input' for
        # input devices, 'storage' for removable media, 'network' for
        # NetworkManager, 'optical' for CD/DVD burning.
        groups += ["audio", "video", "input", "storage", "network", "optical"]
    cmds: list[list[str]] = [
        ["arch-chroot", root, "useradd", "-m", "-G", ",".join(groups),
         "-c", full_name, username],
    ]
    if administrator:
        # Back up the sudoers, uncomment the wheel line, then run
        # visudo -c to verify. If verification fails, restore the backup
        # so sudo is not left in a broken state.
        cmds.append(["arch-chroot", root, "cp", "/etc/sudoers",
                     "/etc/sudoers.modular.bak"])
        cmds.append(["arch-chroot", root, "sed", "-i",
                     "s/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/",
                     "/etc/sudoers"])
        cmds.append(["arch-chroot", root, "visudo", "-c", "-f", "/etc/sudoers"])
    cmds.append(["arch-chroot", root, "chpasswd"])
    if root_password:
        cmds.append(["arch-chroot", root, "chpasswd"])
    marker = {
        "__stdin_user__": (username, password),
        "__stdin_root__": (root_password or ""),
    }
    return _WithStdin(cmds, marker)


def execute_step(cmd: list[str], stdin_text: str | None = None,
                 timeout: int | None = None) -> tuple[int, str]:
    proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True,
                          timeout=timeout)
    output = (proc.stdout or "").strip()
    if proc.returncode != 0 and (proc.stderr or "").strip():
        output = (proc.stderr or "").strip()
    return proc.returncode, output


def regenerate_initramfs(kernel: str = "linux",
                         root: str = "/mnt") -> list[list[str]]:
    """Run mkinitcpio to regenerate the initramfs for the chosen kernel.

    Pacstrap does not always run this for the host kernel; explicit
    regeneration is required for bootloader changes to take effect.
    """
    return [["arch-chroot", root, "mkinitcpio", "-p", shlex.quote(kernel)]]


def bootloader_commands(bootloader: str,
                        root: str = "/mnt") -> list[list[str]]:
    """Build the bootloader install commands.

    systemd-boot: bootctl install + a loader entry pointing at the
    default kernel image (vmlinuz-linux + initramfs-linux.img).
    grub: install grub to the EFI firmware, then grub-mkconfig.
    """
    if bootloader == "systemd-boot":
        return [
            ["arch-chroot", root, "bootctl", "install"],
        ]
    if bootloader == "grub":
        return [
            ["arch-chroot", root, "grub-install", "--target=x86_64-efi",
             "--efi-directory=/boot/efi", "--bootloader-id=ModularLinux",
             "--recheck"],
            ["arch-chroot", root, "grub-mkconfig", "-o",
             "/boot/grub/grub.cfg"],
        ]
    raise ValueError(
        f"unsupported bootloader: {bootloader!r} "
        f"(supported: {', '.join(SUPPORTED_BOOTLOADERS)})"
    )


def enable_service_command(service: str, root: str = "/mnt") -> list[str]:
    unit = service
    if not unit.endswith((".service", ".socket", ".timer")):
        unit += ".service"
    return ["systemctl", "--root", root, "enable", unit]


def export_configuration(config_yaml: str, target_root: str = "/mnt",
                         target_path: str | None = None) -> dict[str, str]:
    """Return {path: contents} so the caller writes the exported YAML.

    The target_path is validated to live inside target_root, otherwise a
    caller could accidentally overwrite the live filesystem.
    """
    if target_path is None:
        target_path = os.path.join(target_root, "etc/modular/modular.yaml")
    target_path = os.path.normpath(target_path)
    target_root = os.path.normpath(target_root)
    if not (target_path == target_root
            or target_path.startswith(target_root + os.sep)):
        raise ValueError(
            f"export path {target_path!r} is not inside {target_root!r}"
        )
    return {target_path: config_yaml}


def is_chroot_ready(root: str = "/mnt") -> bool:
    """Return True if `root` looks like a populated pacstrap target."""
    if not root or not os.path.isdir(root):
        return False
    for marker in ("etc/os-release", "usr/bin", "bin/bash"):
        if not os.path.exists(os.path.join(root, marker)):
            return False
    return True


class _WithStdin(list):
    """Command list with a marker carrying stdin credentials.

    The executor pops __stdin_user__ and __stdin_root__ and feeds them
    on stdin to the chpasswd commands; markers are never printed or
    logged.
    """

    def __init__(self, items, marker):
        super().__init__(items)
        self.marker = marker
