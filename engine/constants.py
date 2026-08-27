"""Single source of truth for v1 configuration enums.

Every other module (validation, Go-side mirror, installer UI, schema)
imports from here so adding a new desktop or shell only requires one
change. The Go CLI keeps its own mirror of these constants in
cmd/modular/config.go; the round-trip is verified by test_consistency.
"""

from __future__ import annotations

SUPPORTED_KERNELS: tuple[str, ...] = (
    "linux", "linux-lts", "linux-zen", "linux-hardened",
)
SUPPORTED_FILESYSTEMS: tuple[str, ...] = ("ext4", "btrfs")
SUPPORTED_BOOTLOADERS: tuple[str, ...] = ("systemd-boot", "grub")
SUPPORTED_SHELLS: tuple[str, ...] = ("bash", "zsh", "fish")
SUPPORTED_GPU_MODES: tuple[str, ...] = (
    "automatic", "open-source", "nvidia-proprietary", "manual",
)
SUPPORTED_LOGIN_MANAGERS: tuple[str, ...] = (
    "sddm", "gdm", "lightdm", "ly", "none",
)
SUPPORTED_INIT_SYSTEMS: tuple[str, ...] = ("systemd",)
SUPPORTED_ARCHITECTURES: tuple[str, ...] = ("x86_64",)
SUPPORTED_DISTRIBUTIONS: tuple[str, ...] = ("arch",)
SUPPORTED_DISPLAY_PROTOCOLS: tuple[str, ...] = ("wayland", "x11", "automatic")
SUPPORTED_DESKTOPS: tuple[str, ...] = (
    "kde", "gnome", "xfce", "cinnamon", "mate", "lxqt",
    "lxde", "budgie", "cosmic", "hyprland",
)
SUPPORTED_WMS: tuple[str, ...] = (
    "sway", "i3", "openbox", "awesome", "bspwm", "river", "labwc",
)
SUPPORTED_ENVIRONMENTS: tuple[str, ...] = (
    SUPPORTED_DESKTOPS + SUPPORTED_WMS + ("none",)
)
KNOWN_HARDWARE: tuple[str, ...] = (
    "network", "wifi", "bluetooth", "audio", "webcam",
    "printing", "scanner", "vpn",
)
KNOWN_ROLES: tuple[str, ...] = (
    "general", "developer", "ai-ml", "gaming", "creator",
    "student", "server", "security",
)
TRUSTED_SOURCES: tuple[str, ...] = ("arch",)
THIRD_PARTY_SOURCES: tuple[str, ...] = ("aur", "flatpak", "appimage")
ALL_SOURCES: tuple[str, ...] = TRUSTED_SOURCES + THIRD_PARTY_SOURCES

# Default for desktop.environment when the user picks "no desktop".
NO_DESKTOP = "none"


def login_manager_for(desktop_id: str) -> str | None:
    """Per spec §27: derive the display manager from the desktop choice."""
    from .packages import DESKTOP_LOGIN_MANAGER  # noqa: F401  (kept for back-compat)
    env = desktop_id.removeprefix("desktop.").removeprefix("wm.")
    return DESKTOP_LOGIN_MANAGER.get(env)
