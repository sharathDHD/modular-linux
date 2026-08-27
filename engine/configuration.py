"""modular.yaml v1 configuration model (spec §30, §54)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

from .errors import ConfigurationError


@dataclass
class ModularConfiguration:
    version: str = "1"
    distribution: str = "arch"
    architecture: str = "x86_64"
    init: str = "systemd"
    kernel: str = "linux"
    desktop_environment: str = "none"
    display: str = "automatic"
    login_manager: str | None = None
    gpu_mode: str = "automatic"
    hardware: dict[str, object] = field(default_factory=dict)
    roles: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    shell_type: str = "bash"
    filesystem_type: str = "ext4"
    bootloader_type: str = "systemd-boot"
    sources: dict[str, bool] = field(
        default_factory=lambda: {"arch": True, "aur": False,
                                 "flatpak": False, "appimage": False})

    def selected_hardware(self) -> list[str]:
        return sorted(k for k, v in self.hardware.items() if v is True)

    @classmethod
    def from_dict(cls, data: dict) -> "ModularConfiguration":
        base = data.get("base") or {}
        system = data.get("system") or {}
        desktop = data.get("desktop") or {}
        filesystem = data.get("filesystem") or {}
        bootloader = data.get("bootloader") or {}
        shell = data.get("shell") or {}
        sources_raw = data.get("sources") or {}

        hardware_raw = data.get("hardware") or {}
        gpu_mode = hardware_raw.pop("gpu", "automatic")
        if not isinstance(gpu_mode, str):
            gpu_mode = "automatic"

        sources = {"arch": True, "aur": False, "flatpak": False,
                   "appimage": False}
        for key in sources:
            if isinstance(sources_raw.get(key), bool):
                sources[key] = sources_raw[key]

        return cls(
            version=str(data.get("version", "1")),
            distribution=base.get("distribution", "arch"),
            architecture=system.get("architecture", "x86_64"),
            init=system.get("init", "systemd"),
            kernel=system.get("kernel", "linux"),
            desktop_environment=desktop.get("environment", "none"),
            display=desktop.get("display", "automatic"),
            login_manager=desktop.get("login_manager"),
            gpu_mode=gpu_mode,
            hardware={k: v for k, v in hardware_raw.items()},
            roles=list(data.get("roles") or []),
            applications=list(data.get("applications") or []),
            shell_type=shell.get("type", "bash"),
            filesystem_type=filesystem.get("type", "ext4"),
            bootloader_type=bootloader.get("type", "systemd-boot"),
            sources=sources,
        )

    @classmethod
    def load(cls, path: str) -> "ModularConfiguration":
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except OSError as exc:
            raise ConfigurationError(f"cannot read {path}: {exc}") from exc
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigurationError("configuration must be a YAML mapping")
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        desktop = {"environment": self.desktop_environment}
        if self.desktop_environment != "none":
            desktop["display"] = self.display
            if self.login_manager:
                desktop["login_manager"] = self.login_manager
        hardware = {k: v for k, v in sorted(self.hardware.items())
                    if v is not None and v is not False}
        if self.gpu_mode != "automatic":
            hardware["gpu"] = self.gpu_mode
        return {
            "version": 1,
            "base": {"distribution": self.distribution},
            "system": {"architecture": self.architecture,
                       "kernel": self.kernel, "init": self.init},
            "desktop": desktop,
            "hardware": hardware,
            "roles": list(self.roles),
            "applications": list(self.applications),
            "shell": {"type": self.shell_type},
            "filesystem": {"type": self.filesystem_type},
            "bootloader": {"type": self.bootloader_type},
            "sources": dict(self.sources),
        }

    def save(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.to_dict(), fh, sort_keys=False)

    @staticmethod
    def export_target() -> str:
        return "/etc/modular/modular.yaml"
