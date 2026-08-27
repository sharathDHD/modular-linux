"""Installation plan generation (v1.0, spec §14/§23/§30/§34).

The plan is generated and validated *before* any disk modification occurs.
Kernel selection swaps the kernel package in the base set; GPU mode selects
the gpu.* profile at resolution time.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

SUPPORTED_KERNELS = ("linux", "linux-lts", "linux-zen", "linux-hardened")
SUPPORTED_FILESYSTEMS = ("ext4", "btrfs")
SUPPORTED_BOOTLOADERS = ("systemd-boot", "grub")
SUPPORTED_SHELLS = ("bash", "zsh", "fish")
SUPPORTED_GPU_MODES = ("automatic", "open-source", "nvidia-proprietary",
                       "manual")
SUPPORTED_LOGIN_MANAGERS = ("sddm", "gdm", "lightdm", "ly", "none")

# Derived per spec §27 unless the user overrides it.
DESKTOP_LOGIN_MANAGER = {
    "kde": "sddm",
    "gnome": "gdm",
    "xfce": "lightdm",
    "cinnamon": "lightdm",
    "mate": "lightdm",
    "lxqt": "sddm",
    "lxde": "lightdm",
    "budgie": "lightdm",
    "cosmic": "cosmic-greeter",
    "hyprland": "ly",
    "sway": "ly",
}

TRUSTED_SOURCES = ("arch",)
THIRD_PARTY_SOURCES = ("aur", "flatpak", "appimage")


def base_packages(kernel: str = "linux") -> list[str]:
    if kernel not in SUPPORTED_KERNELS:
        raise ValueError(f"unsupported kernel: {kernel}")
    return ["base", kernel, "linux-firmware", "sudo"]


@dataclass
class InstallationPlan:
    version: str = "1"
    distribution: str = "arch"
    architecture: str = "x86_64"
    init: str = "systemd"
    kernel: str = "linux"
    base_packages: list[str] = field(default_factory=lambda: base_packages())
    packages: list[str] = field(default_factory=list)
    aur_packages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    filesystem: str = "ext4"
    bootloader: str = "systemd-boot"
    shell: str = "bash"
    display: str | None = None
    login_manager: str | None = None
    desktop: str | None = None
    roles: list[str] = field(default_factory=list)
    hardware: list[str] = field(default_factory=list)
    sources: dict[str, bool] = field(
        default_factory=lambda: {"arch": True, "aur": False,
                                 "flatpak": False, "appimage": False})

    def to_dict(self) -> dict:
        return asdict(self)

    def all_packages(self) -> list[str]:
        return sorted(set(self.base_packages) | set(self.packages))


def derive_login_manager(desktop_id: str,
                         override: str | None = None) -> str | None:
    """DM selection derived from desktop unless explicitly overridden (§27)."""
    if override and override != "automatic":
        if override not in SUPPORTED_LOGIN_MANAGERS:
            raise ValueError(f"unsupported login manager: {override}")
        return override
    env = desktop_id.removeprefix("desktop.").removeprefix("wm.")
    return DESKTOP_LOGIN_MANAGER.get(env)


def build_plan(resolution,
               kernel: str = "linux",
               filesystem: str = "ext4",
               bootloader: str = "systemd-boot",
               shell: str = "bash",
               desktop_id: str | None = None,
               login_manager: str | None = None,
               roles: list[str] | None = None,
               hardware: list[str] | None = None,
               sources: dict[str, bool] | None = None) -> InstallationPlan:
    sources = sources or {"arch": True, "aur": False, "flatpak": False,
                          "appimage": False}
    official, aur = [], []
    for pkg in resolution.packages:
        (aur if pkg.startswith("aur:") else official).append(pkg)
    return InstallationPlan(
        kernel=kernel,
        base_packages=base_packages(kernel),
        packages=official,
        aur_packages=aur,
        services=list(resolution.services),
        filesystem=filesystem,
        bootloader=bootloader,
        shell=shell,
        display=resolution.display_protocol,
        login_manager=derive_login_manager(desktop_id or "", login_manager),
        desktop=desktop_id,
        roles=list(roles or []),
        hardware=list(hardware or []),
        sources=sources,
    )
