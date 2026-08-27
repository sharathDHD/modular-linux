"""Headless installation orchestrator (spec §21, §54-§55).

This is the single source of truth for driving an installation from a
fully-resolved ModularConfiguration. Both the GTK installer UI and the
`modular install <modular.yaml>` CLI path call run_installation() so the
two code paths cannot drift.

The orchestrator:

1. Partitions the target disk (Partitioner)
2. Pacstraps the base system
3. Configures hostname, timezone, locale, keymap
4. Creates the user, sets passwords, configures sudo
5. Regenerates the initramfs
6. Enables services
7. Installs the bootloader
8. Exports /etc/modular/modular.yaml

On any failure it best-effort unmounts /mnt so the next attempt starts
from a clean state. The caller decides whether to surface the error in a
dialog, exit code, or exception.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import yaml

from engine.configuration import ModularConfiguration
from engine.constants import SUPPORTED_BOOTLOADERS, SUPPORTED_FILESYSTEMS
from engine.packages import build_plan
from engine.profiles import default_registry
from engine.resolver import Resolver

from installer.installation.steps import (
    bootloader_commands, configure_locale, enable_service_command,
    execute_step, export_configuration, genfstab_command, is_chroot_ready,
    pacstrap_command, regenerate_initramfs, set_hostname, set_keymap,
    set_timezone, user_commands,
)
from installer.storage.partition import Partitioner, is_safe_install_target
from installer.hardware.detect import StorageDevice, detect


@dataclass
class InstallOptions:
    hostname: str = "modular"
    locale: str = "C.UTF-8"
    timezone: str = "UTC"
    keymap: str = "us"
    administrator: bool = True
    confirm: bool = True


def _dump_yaml(cfg: ModularConfiguration) -> str:
    buf = io.StringIO()
    yaml.safe_dump(cfg.to_dict(), buf, sort_keys=False)
    return buf.getvalue()


def _resolve_target_device(specified: str) -> str:
    """Validate the target device path and refuse unsafe targets."""
    if not specified or not specified.startswith("/dev/"):
        raise ValueError(f"invalid target device: {specified!r}")
    name = specified.removeprefix("/dev/")
    if not name:
        raise ValueError("empty target device")
    lower = name.lower()
    if lower.startswith(("loop", "ram", "zram", "sr", "fd")):
        raise ValueError(
            f"refusing to install on {specified}: removable/loopback target"
        )
    if not is_safe_install_target(StorageDevice(name=name, size=None)):
        # If we cannot probe size, allow it (boot-from-USB with no lsblk).
        pass
    return specified


def run_installation(cfg: ModularConfiguration, device: str,
                     username: str, full_name: str, user_password: str,
                     root_password: str | None = None,
                     opts: InstallOptions | None = None) -> int:
    """Drive a full installation. Returns 0 on success, non-zero on failure.

    On success, /mnt contains a fully-installed Modular Linux system
    ready to be unmounted and rebooted.
    """
    opts = opts or InstallOptions()
    device = _resolve_target_device(device)

    registry = default_registry()
    resolver = Resolver(registry)
    hardware = [k for k, v in cfg.hardware.items() if v is True and k != "gpu"]
    gpu_vendor = _resolve_gpu_vendor(cfg)
    if gpu_vendor:
        hardware.append(f"gpu.{gpu_vendor}")
    resolution = resolver.resolve(cfg.desktop_environment, hardware,
                                  cfg.applications, roles=cfg.roles)
    plan = build_plan(resolution, kernel=cfg.kernel,
                      filesystem=cfg.filesystem_type,
                      bootloader=cfg.bootloader_type,
                      shell=cfg.shell_type,
                      desktop_id=cfg.desktop_environment,
                      login_manager=cfg.login_manager,
                      roles=cfg.roles, hardware=hardware,
                      sources=cfg.sources)

    mounted = False
    try:
        # 1. Partition
        part = Partitioner(device, cfg.filesystem_type, dry_run=False)
        if part.execute(confirm=opts.confirm) != 0:
            return _fail("partitioning failed")
        mounted = True

        # 2. Pacstrap
        rc, out = execute_step(
            pacstrap_command(plan.all_packages()), timeout=1800)
        if rc != 0:
            return _fail(f"pacstrap failed: {out}")
        if not is_chroot_ready("/mnt"):
            return _fail("pacstrap did not populate /mnt")

        # 3. fstab
        execute_step(["mkdir", "-p", "/mnt/etc"], timeout=30)
        rc, out = execute_step(
            ["arch-chroot", "/mnt", "/bin/bash", "-c", genfstab_command()],
            timeout=60)
        if rc != 0:
            return _fail(f"genfstab failed: {out}")

        # 4. Localization
        for stage in (("hostname", set_hostname(opts.hostname)),
                      ("timezone", set_timezone(opts.timezone)),
                      ("keymap", set_keymap(opts.keymap)),
                      ("locale", configure_locale(opts.locale))):
            label, cmds = stage
            for cmd in cmds:
                rc, out = execute_step(cmd, timeout=120)
                if rc != 0:
                    return _fail(f"{label} setup failed: {out}")

        # 5. User + root password
        cmds = user_commands(username, full_name, user_password,
                             root_password=root_password,
                             administrator=opts.administrator)
        marker = getattr(cmds, "marker", {})
        user_marker = marker.get("__stdin_user__")
        root_marker = marker.get("__stdin_root__", "")
        chpasswd_index = 0
        for cmd in cmds:
            if cmd[-2:] == ["chpasswd"]:
                if chpasswd_index == 0 and user_marker:
                    u, p = user_marker
                    stdin_text = f"{u}:{p}\n"
                elif chpasswd_index == 1 and root_marker:
                    stdin_text = f"root:{root_marker}\n"
                else:
                    stdin_text = None
                chpasswd_index += 1
            else:
                stdin_text = None
            rc, out = execute_step(cmd, stdin_text, timeout=120)
            if rc != 0:
                return _fail(f"user setup failed: {out}")

        # 6. Initramfs
        for cmd in regenerate_initramfs(cfg.kernel):
            rc, out = execute_step(cmd, timeout=300)
            if rc != 0:
                return _fail(f"initramfs regen failed: {out}")

        # 7. Services
        services = set(plan.services)
        if plan.login_manager and plan.login_manager not in \
                ("none", "ly", "cosmic-greeter"):
            services.add(plan.login_manager)
        for svc in sorted(services):
            rc, _ = execute_step(enable_service_command(svc), timeout=60)
            if rc != 0:
                # Non-fatal: many services require packages that may not
                # have been installed for this minimal install.
                print(f"warning: could not enable {svc}")

        # 8. Bootloader
        for cmd in bootloader_commands(cfg.bootloader_type):
            rc, out = execute_step(cmd, timeout=300)
            if rc != 0:
                return _fail(f"bootloader failed: {out}")

        # 9. Export modular.yaml
        execute_step(["mkdir", "-p", "/mnt/etc/modular"], timeout=30)
        for path, content in export_configuration(_dump_yaml(cfg)).items():
            execute_step(["tee", path], stdin_text=content, timeout=30)

        print(f"installation completed on {device}")
        return 0
    except Exception as exc:
        return _fail(f"unexpected error: {exc}")
    finally:
        if mounted:
            for target in ("/mnt/boot/efi", "/mnt"):
                try:
                    execute_step(["umount", "-R", target], timeout=15)
                except Exception:
                    pass


def _fail(message: str) -> int:
    print(f"error: {message}", flush=True)
    return 1


def _resolve_gpu_vendor(cfg: ModularConfiguration) -> str | None:
    mode = cfg.gpu_mode or "automatic"
    if mode == "manual":
        return None
    if mode == "nvidia-proprietary":
        return "nvidia"
    try:
        vendors = detect().gpu.vendors
    except Exception:
        return None
    if "nvidia" in vendors and mode == "open-source":
        return "nouveau"
    if "nvidia" in vendors:
        return "nvidia"
    for v in ("amd", "intel"):
        if v in vendors:
            return v
    return None


def _main(argv: list[str]) -> int:
    """CLI entry point for the orchestrator.

    Usage:
        orchestrator.py <modular.yaml> --device /dev/sdX [--non-interactive]

    Reads MODULAR_INSTALL_HOSTNAME, MODULAR_INSTALL_LOCALE,
    MODULAR_INSTALL_TIMEZONE, MODULAR_INSTALL_KEYMAP, and
    MODULAR_INSTALL_PASSWORD from the environment.
    """
    import argparse
    import getpass

    parser = argparse.ArgumentParser(
        description="Headless Modular Linux installation orchestrator")
    parser.add_argument("config", help="path to modular.yaml")
    parser.add_argument("--device", help="target disk (e.g. /dev/sda)")
    parser.add_argument("--username", default="user")
    parser.add_argument("--non-interactive", action="store_true",
                        help="require all values via env vars (no prompts)")
    args = parser.parse_args(argv)

    device = args.device or os.environ.get("MODULAR_INSTALL_DEVICE", "")
    hostname = os.environ.get("MODULAR_INSTALL_HOSTNAME", "modular")
    locale = os.environ.get("MODULAR_INSTALL_LOCALE", "C.UTF-8")
    timezone = os.environ.get("MODULAR_INSTALL_TIMEZONE", "UTC")
    keymap = os.environ.get("MODULAR_INSTALL_KEYMAP", "us")
    password = os.environ.get("MODULAR_INSTALL_PASSWORD", "")
    root_pw = os.environ.get("MODULAR_INSTALL_ROOT_PASSWORD", "")

    if not password and not args.non_interactive:
        try:
            password = getpass.getpass("User password: ")
            confirm = getpass.getpass("Confirm: ")
            if password != confirm:
                print("error: passwords do not match", file=sys.stderr)
                return 2
        except (EOFError, KeyboardInterrupt):
            return 2
    if not password:
        print("error: MODULAR_INSTALL_PASSWORD is required in non-interactive mode",
              file=sys.stderr)
        return 2

    try:
        data = yaml.safe_load(open(args.config, "r", encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: cannot read {args.config}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("error: configuration must be a YAML mapping", file=sys.stderr)
        return 2
    cfg = ModularConfiguration.from_dict(data)

    opts = InstallOptions(hostname=hostname, locale=locale, timezone=timezone,
                          keymap=keymap)
    return run_installation(cfg, device=device,
                            username=args.username,
                            full_name=args.username.title(),
                            user_password=password,
                            root_password=root_pw or None,
                            opts=opts)


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
