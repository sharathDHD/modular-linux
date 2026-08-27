"""Configuration validation for modular.yaml v1 (spec §30, §51)."""

from __future__ import annotations

from typing import Any

import yaml

from .errors import ConfigurationError
from .packages import (
    SUPPORTED_BOOTLOADERS,
    SUPPORTED_FILESYSTEMS,
    SUPPORTED_GPU_MODES,
    SUPPORTED_KERNELS,
    SUPPORTED_LOGIN_MANAGERS,
    SUPPORTED_SHELLS,
)
from .profiles import ProfileRegistry

SUPPORTED_DESKTOPS = ("kde", "gnome", "xfce", "cinnamon", "mate", "lxqt",
                      "lxde", "budgie", "cosmic", "hyprland")
SUPPORTED_WMS = ("sway", "i3", "openbox", "awesome", "bspwm", "river",
                 "labwc", "none")
SUPPORTED_ENVIRONMENTS = SUPPORTED_DESKTOPS + SUPPORTED_WMS
KNOWN_ROLES = ("general", "developer", "ai-ml", "gaming", "creator",
               "student", "server", "security")
KNOWN_HARDWARE = ("network", "wifi", "bluetooth", "audio", "webcam",
                  "printing", "scanner", "vpn")
DISPLAY_PROTOCOLS = ("wayland", "x11", "automatic")


def load_configuration(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        raise ConfigurationError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("configuration must be a YAML mapping")
    return data


def validate(data: dict[str, Any], registry: ProfileRegistry | None = None) -> list[str]:
    """Return a list of validation error strings. Empty list means valid."""
    errors: list[str] = []

    version = str(data.get("version"))
    if version not in ("1", "1.0"):
        errors.append(f"unsupported configuration version: {data.get('version')} "
                      "(expected 1)")

    base = data.get("base") or {}
    if base.get("distribution") not in (None, "arch"):
        errors.append(f"unsupported distribution: {base.get('distribution')}")

    system = data.get("system") or {}
    arch = system.get("architecture", "x86_64")
    if arch != "x86_64":
        errors.append(f"unsupported architecture: {arch}")
    init = system.get("init", "systemd")
    if init != "systemd":
        errors.append(f"unsupported init system: {init}")
    kernel = system.get("kernel", "linux")
    if kernel not in SUPPORTED_KERNELS:
        errors.append(f"unknown kernel '{kernel}' "
                      f"(expected one of {', '.join(SUPPORTED_KERNELS)})")

    desktop = data.get("desktop") or {}
    env = desktop.get("environment", "none")
    if env != "none" and env not in SUPPORTED_ENVIRONMENTS:
        errors.append(
            f"unknown desktop environment '{env}' "
            f"(expected one of {', '.join(SUPPORTED_ENVIRONMENTS)})"
        )
    display = desktop.get("display", "automatic")
    if display not in DISPLAY_PROTOCOLS:
        errors.append(f"unknown display protocol: {display}")
    login_manager = desktop.get("login_manager")
    if login_manager and login_manager != "automatic" \
            and login_manager not in SUPPORTED_LOGIN_MANAGERS:
        errors.append(f"unknown login manager: {login_manager}")

    hardware = data.get("hardware") or {}
    if not isinstance(hardware, dict):
        errors.append("'hardware' must be a mapping of feature -> bool/value")
    else:
        unknown = set(hardware) - set(KNOWN_HARDWARE) - {"gpu"}
        if unknown:
            errors.append(f"unknown hardware features: {', '.join(sorted(unknown))}")
        gpu_mode = hardware.get("gpu", "automatic")
        if gpu_mode not in SUPPORTED_GPU_MODES:
            errors.append(f"unknown GPU mode '{gpu_mode}' "
                          f"(expected one of {', '.join(SUPPORTED_GPU_MODES)})")

    roles = data.get("roles") or []
    if not isinstance(roles, list):
        errors.append("'roles' must be a list")
    else:
        for role in roles:
            role_id = role if "." in role else f"role.{role}"
            if registry is not None and not registry.has(role_id):
                errors.append(f"unknown role profile: {role_id}")

    applications = data.get("applications") or []
    if not isinstance(applications, list):
        errors.append("'applications' must be a list")
    else:
        aur_selected = False
        flatpak_selected = False
        for app in applications:
            app_id = app if app.startswith("app.") else f"app.{app}"
            profile = registry.get(app_id) if registry is not None else None
            if registry is not None and profile is None:
                errors.append(f"unknown application profile: {app_id}")
                continue
            source = getattr(profile, "source", None) if profile else None
            if source == "aur":
                aur_selected = True
            elif source == "flatpak":
                flatpak_selected = True
        sources = data.get("sources") or {}
        if aur_selected and not sources.get("aur"):
            errors.append(
                "configuration selects AUR applications but sources.aur is "
                "disabled; third-party sources must be enabled explicitly"
            )
        if flatpak_selected and not sources.get("flatpak"):
            errors.append(
                "configuration selects Flatpak applications but "
                "sources.flatpak is disabled; enable it explicitly"
            )

    shell = (data.get("shell") or {}).get("type", "bash")
    if shell not in SUPPORTED_SHELLS:
        errors.append(f"unsupported shell '{shell}' "
                      f"(supported: {', '.join(SUPPORTED_SHELLS)})")

    filesystem = (data.get("filesystem") or {}).get("type", "ext4")
    if filesystem not in SUPPORTED_FILESYSTEMS:
        errors.append(
            f"unsupported filesystem '{filesystem}' "
            f"(supported: {', '.join(SUPPORTED_FILESYSTEMS)})"
        )

    bootloader = (data.get("bootloader") or {}).get("type", "systemd-boot")
    if bootloader not in SUPPORTED_BOOTLOADERS:
        errors.append(
            f"unsupported bootloader '{bootloader}' "
            f"(supported: {', '.join(SUPPORTED_BOOTLOADERS)})"
        )

    return errors
