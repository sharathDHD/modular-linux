"""Service resolution helpers."""

from __future__ import annotations


def normalize_services(services: list[str]) -> list[str]:
    """Deduplicate, sort, and strip empty service names."""
    seen: set[str] = set()
    out: list[str] = []
    for svc in services:
        name = svc.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return sorted(out)


def systemd_enable_commands(services: list[str], root: str = "/mnt") -> list[list[str]]:
    """Build arch-chroot-relative systemctl enable commands."""
    commands = []
    for svc in normalize_services(services):
        unit = svc if svc.endswith((".service", ".socket", ".timer")) else f"{svc}.service"
        commands.append(["systemctl", "--root", root, "enable", unit])
    return commands
