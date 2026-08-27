"""Installation steps orchestrating upstream Arch tools (spec §7, §14).

Every step returns the command it would run; nothing executes unless
run=True is passed by the installer after explicit user confirmation.
"""

from __future__ import annotations

import os


def pacstrap_command(packages: list[str], root: str = "/mnt") -> list[str]:
    return ["pacstrap", "-K", root] + list(packages)


def genfstab_command(root: str = "/mnt") -> str:
    return f"genfstab -U {root} >> {root}/etc/fstab"


def set_timezone(zone: str, root: str = "/mnt") -> list[list[str]]:
    return [
        ["arch-chroot", root, "ln", "-sf",
         f"/usr/share/zoneinfo/{zone}", "/etc/localtime"],
        ["arch-chroot", root, "hwclock", "--systohc"],
    ]


def set_hostname(hostname: str, root: str = "/mnt") -> dict[str, str]:
    return {
        f"{root}/etc/hostname": hostname + "\n",
        f"{root}/etc/hosts":
            f"127.0.0.1\tlocalhost\n::1\tlocalhost\n127.0.1.1\t{hostname}\n",
    }


def user_commands(username: str, full_name: str, password: str,
                  administrator: bool = True,
                  root: str = "/mnt") -> list[list[str]]:
    groups = ["wheel"] if administrator else []
    cmds = [
        ["arch-chroot", root, "useradd", "-m", "-G", ",".join(groups),
         "-c", full_name, username],
    ]
    if administrator:
        cmds.append(["arch-chroot", root, "sed", "-i",
                     "s/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/",
                     "/etc/sudoers"])
    # chpasswd receives the password on stdin; never via argv or logs.
    chpasswd = ["arch-chroot", root, "chpasswd"]
    env_marker = {"__stdin_password__": (username, password)}
    return _WithStdin(cmds + [chpasswd], env_marker)


class _WithStdin(list):
    """Command list with a marker carrying stdin credentials.

    The executor pops __stdin_password__ and feeds it to the last command's
    stdin; the marker is never printed or logged.
    """

    def __init__(self, items, marker):
        super().__init__(items)
        self.marker = marker


def execute_step(cmd: list[str], stdin_text: str | None = None) -> tuple[int, str]:
    import subprocess

    proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True)
    output = proc.stdout.strip()
    if proc.returncode != 0 and proc.stderr.strip():
        output = proc.stderr.strip()
    return proc.returncode, output


def bootloader_commands(bootloader: str, root: str = "/mnt") -> list[list[str]]:
    if bootloader != "systemd-boot":
        raise ValueError(f"unsupported bootloader: {bootloader}")
    return [
        ["arch-chroot", root, "bootctl", "install"],
    ]


def enable_service_command(service: str, root: str = "/mnt") -> list[str]:
    unit = service
    if not unit.endswith((".service", ".socket", ".timer")):
        unit += ".service"
    return ["systemctl", "--root", root, "enable", unit]


def export_configuration(config_yaml: str, target_root: str = "/mnt",
                         target_path: str | None = None) -> dict[str, str]:
    path = target_path or os.path.join(target_root, "etc/modular/modular.yaml")
    return {path: config_yaml}
