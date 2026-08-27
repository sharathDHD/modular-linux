"""Python CLI fallback (spec §23).

The Go binary in bin/modular is the primary CLI; this module provides the
same commands for development environments without a Go toolchain.

    python -m cli list desktops
    python -m cli hardware
    python -m cli resolve kde firefox audio
    python -m cli validate examples/modular.yaml
    python -m cli generate-plan examples/modular.yaml
    python -m cli install examples/modular.yaml
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from engine.configuration import ModularConfiguration
from engine.errors import ModularError
from engine.packages import build_plan
from engine.profiles import default_registry
from engine.resolver import Resolver
from engine.validation import load_configuration, validate


def _usage() -> int:
    print(__doc__)
    return 2


def main(argv: list[str]) -> int:
    if not argv:
        return _usage()
    registry = default_registry()
    cmd, rest = argv[0], argv[1:]

    if cmd == "list" and rest:
        group = {"desktops": "desktop", "hardware": "hardware",
                 "applications": "applications", "profiles": None,
                 "roles": "roles", "wms": "wm", "gpu": "gpu"}[rest[0]]
        profiles = registry.all() if group is None \
            else registry.by_category(group)
        for p in profiles:
            src = f" [{p.source}]" if getattr(p, "source", None) else ""
            print(f"{p.id:<24} {p.category:<16} {p.name}{src}")
        return 0

    if cmd == "hardware":
        from installer.hardware.detect import detect
        info = detect()
        for line in [
            f"CPU      : {info.cpu.model} ({info.cpu.cores} cores)",
            f"Memory   : {info.memory.total_mb} MB",
            f"GPU      : {', '.join(info.gpu.devices) or 'unknown'}",
        ] + [f"Disk     : {d.name} {d.size or ''} {d.model or ''}"
             for d in info.storage] + [
            f"Ethernet : {'yes' if info.ethernet else 'no'}",
            f"Wi-Fi    : {'yes' if info.wifi else 'no'}",
            f"Bluetooth: {'yes' if info.bluetooth else 'no'}",
            f"Audio    : {'yes' if info.audio else 'no'}",
            f"Webcam   : {'yes' if info.webcam else 'no'}",
        ]:
            print(line)
        return 0

    if cmd == "resolve":
        desktop = None
        hardware: list[str] = []
        applications: list[str] = []
        roles: list[str] = []
        for arg in rest:
            if arg.startswith("desktop.") or arg in ("kde", "gnome", "xfce",
                                                     "hyprland"):
                desktop = arg.removeprefix("desktop.")
            elif arg.startswith("role.") or arg in (
                    "general", "developer", "ai-ml", "gaming", "creator",
                    "student", "server", "security"):
                roles.append(arg if "." in arg else f"role.{arg}")
            elif "." in arg:
                hardware.append(arg)
            else:
                applications.append(arg)
        res = Resolver(registry).resolve(desktop, hardware, applications,
                                         roles=roles)
        print("profiles :", ", ".join(p.id for p in res.selected))
        print("packages :", ", ".join(res.packages))
        print("services :", ", ".join(res.services))
        print("display  :", res.display_protocol or "-")
        return 0

    if cmd == "validate" and rest:
        data = load_configuration(rest[0])
        errors = validate(data, registry)
        if errors:
            for e in errors:
                print("INVALID:", e)
            return 1
        print(f"OK: {rest[0]} is valid")
        return 0

    if cmd == "generate-plan" and rest:
        data = load_configuration(rest[0])
        errors = validate(data, registry)
        if errors:
            for e in errors:
                print("INVALID:", e, file=sys.stderr)
            return 1
        cfg = ModularConfiguration.from_dict(data)
        hardware = [k for k in cfg.hardware
                    if isinstance(cfg.hardware[k], bool)
                    and cfg.hardware[k]]
        gpu_vendor = resolve_gpu(registry, cfg)
        if gpu_vendor:
            hardware.append(f"gpu.{gpu_vendor}")
        res = Resolver(registry).resolve(
            cfg.desktop_environment, hardware, cfg.applications,
            roles=cfg.roles)
        plan = build_plan(res, kernel=cfg.kernel,
                          filesystem=cfg.filesystem_type,
                          bootloader=cfg.bootloader_type,
                          shell=cfg.shell_type,
                          desktop_id=cfg.desktop_environment,
                          login_manager=cfg.login_manager,
                          roles=cfg.roles,
                          hardware=hardware + ([f"gpu.{gpu_vendor}"]
                                               if gpu_vendor else []),
                          sources=cfg.sources)
        print(yaml.safe_dump(plan.to_dict(), sort_keys=False))
        return 0

    if cmd == "install" and rest:
        return _cmd_install(rest[0])

    return _usage()


def _cmd_install(config_path: str) -> int:
    """Run a headless installation from a modular.yaml.

    This is the configuration-driven reproduction path promised by the
    spec (spec §21, §54-§55). It validates the config, resolves the
    plan, then drives the same orchestrator the GUI uses.

    Required prompts are interactive (passwords, target disk). On a
    non-interactive stdin, set MODULAR_INSTALL_PASSWORD and
    MODULAR_INSTALL_DEVICE in the environment.
    """
    data = load_configuration(config_path)
    errors = validate(data, default_registry())
    if errors:
        for e in errors:
            print("INVALID:", e, file=sys.stderr)
        return 1
    cfg = ModularConfiguration.from_dict(data)

    # Resolve device
    device = os.environ.get("MODULAR_INSTALL_DEVICE")
    if not device:
        try:
            device = input("Target disk (e.g. /dev/sda): ").strip()
        except EOFError:
            print("error: no target device provided", file=sys.stderr)
            return 2
    if not device.startswith("/dev/"):
        print(f"error: invalid target device: {device!r}", file=sys.stderr)
        return 2

    # Resolve user / passwords
    username = "user"
    if cfg.applications or cfg.roles or True:
        try:
            entered = input("Username [user]: ").strip()
            if entered:
                username = entered
        except EOFError:
            pass

    password = os.environ.get("MODULAR_INSTALL_PASSWORD")
    if not password:
        try:
            password = getpass.getpass("User password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("error: passwords do not match", file=sys.stderr)
                return 2
        except (EOFError, KeyboardInterrupt):
            print("error: no password provided", file=sys.stderr)
            return 2
    if not password:
        print("error: empty password is not allowed", file=sys.stderr)
        return 2

    root_password = os.environ.get("MODULAR_INSTALL_ROOT_PASSWORD", "")

    from installer.installation.orchestrator import run_installation
    return run_installation(cfg=cfg, device=device, username=username,
                            full_name=username.title(),
                            user_password=password,
                            root_password=root_password or None)


def resolve_gpu(registry, cfg) -> str | None:
    """Map GPU mode + detection to a gpu.* profile (spec §33)."""
    from installer.hardware.detect import detect

    mode = cfg.gpu_mode or "automatic"
    if mode == "manual":
        return None
    if mode == "nvidia-proprietary":
        return "nvidia"
    vendors = detect().gpu.vendors
    if "nvidia" in vendors and mode == "open-source":
        return "nouveau"
    if "nvidia" in vendors:
        return "nvidia"
    for v in ("amd", "intel"):
        if v in vendors:
            return v
    return None


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ModularError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
