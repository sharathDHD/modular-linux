"""Interactive console menu for the netinstall edition.

The netinstall ISO carries only the live system, network drivers and
this menu. Everything the user selects is downloaded from the Arch
mirrors at install time by pacstrap — nothing is pre-baked.

Flow: network pre-flight -> desktop/WM -> hardware -> roles ->
applications -> system choices -> identity -> disk -> plan preview ->
install. Every step goes through `run_installation()`, the same
orchestrator the GTK GUI and the `modular install` CLI use.

Run interactively on the live ISO (autologin shell on tty1 launches
this automatically), or headless-ish for testing:

    python3 -m installer.menu --dry-run

--dry-run stops after writing modular.yaml and printing the plan.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.configuration import ModularConfiguration  # noqa: E402
from engine.errors import ModularError  # noqa: E402
from engine.packages import build_plan  # noqa: E402
from engine.profiles import ProfileRegistry, default_registry  # noqa: E402
from engine.resolver import Resolver  # noqa: E402
from installer.installation.orchestrator import (  # noqa: E402
    InstallOptions, run_installation)

MIRROR_PROBE_URL = "https://geo.mirror.pkgbuild.com/core/os/x86_64/core.db"

FEATURES = [("network", "Networking (ethernet)"), ("wifi", "Wi-Fi"),
            ("bluetooth", "Bluetooth"), ("audio", "Audio"),
            ("webcam", "Webcam"), ("printing", "Printing"),
            ("scanner", "Scanning"), ("vpn", "VPN")]
GPU_MODES = ["automatic", "nvidia", "amd", "intel"]
FILESYSTEMS = ["ext4", "btrfs"]
BOOTLOADERS = ["systemd-boot", "grub"]
SHELLS = ["bash", "zsh", "fish"]
TIMEZONE_DEFAULT = "UTC"
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,62}$")


def check_network(url: str = MIRROR_PROBE_URL,
                  timeout: float = 10.0) -> tuple[bool, str]:
    """Return (reachable, message) for the configured mirror."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout):
            return True, "mirror reachable"
    except Exception as exc:  # noqa: BLE001 — any failure means offline
        return False, str(exc) or exc.__class__.__name__


def list_disk_devices() -> list[tuple[str, str]]:
    """Real install targets from /sys/block: [(path, description)].

    Loop/ram/zram/optical devices are excluded — an installer must never
    offer the media it booted from as an install target.
    """
    devices: list[tuple[str, str]] = []
    base = "/sys/block"
    if not os.path.isdir(base):
        return devices
    for name in sorted(os.listdir(base)):
        if re.match(r"^(loop|ram|zram|sr|fd|dm-)", name):
            continue
        try:
            with open(os.path.join(base, name, "size"),
                      encoding="ascii") as fh:
                sectors = int(fh.read().strip())
        except (OSError, ValueError):
            continue
        if sectors <= 0:
            continue
        size_gib = sectors * 512 / (1024 ** 3)
        model = ""
        for attr in ("device/model", "device/name"):
            try:
                with open(os.path.join(base, name, attr),
                          encoding="utf-8", errors="replace") as fh:
                    model = fh.read().strip()
                    if model:
                        break
            except OSError:
                continue
        desc = f"{size_gib:.1f} GiB" + (f"  {model}" if model else "")
        devices.append((f"/dev/{name}", desc))
    return devices


@dataclass
class MenuResult:
    """Everything the orchestrator needs after a completed menu run."""
    config: ModularConfiguration
    device: str
    username: str
    full_name: str
    user_password: str
    root_password: Optional[str]
    opts: InstallOptions
    config_path: str = ""
    planned_packages: int = 0


def _parse_selection(raw: str, count: int) -> set[int]:
    """Parse '1,3-5' into zero-based indices within range."""
    chosen: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            if lo.isdigit() and hi.isdigit():
                for i in range(int(lo), int(hi) + 1):
                    if 1 <= i <= count:
                        chosen.add(i - 1)
        elif part.isdigit():
            i = int(part)
            if 1 <= i <= count:
                chosen.add(i - 1)
    return chosen


class TextMenu:
    """Console front end building a ModularConfiguration interactively.

    input_fn/print_fn are injectable so the regression tests can drive
    the whole menu with scripted answers (same philosophy as the
    execution-layer tests).
    """

    def __init__(self,
                 input_fn: Callable[[str], str] = input,
                 print_fn: Callable[..., None] = print,
                 network_check: Callable[[], tuple[bool, str]] =
                 lambda: check_network(),
                 registry: ProfileRegistry | None = None,
                 config_path: str = "") -> None:
        self._in = input_fn
        self._out = print_fn
        self._net = network_check
        self.registry = registry or default_registry()
        self.config_path = config_path or self._default_config_path()
        self.dry_run = False

    # ---- helpers -------------------------------------------------------

    @staticmethod
    def _default_config_path() -> str:
        if os.geteuid() == 0:
            return "/root/modular.yaml"
        return os.path.join(os.getcwd(), "modular.yaml")

    def ask(self, prompt: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        answer = self._in(f"{prompt}{suffix}: ").strip()
        return answer or default

    def ask_choice(self, prompt: str, options: list[str],
                   default: str) -> str:
        while True:
            raw = self.ask(f"{prompt} ({'/'.join(options)})", default)
            if raw in options:
                return raw
            self._out(f"  please choose one of: {', '.join(options)}")

    def ask_yes_no(self, prompt: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        while True:
            raw = self.ask(f"{prompt} ({hint})",
                           "y" if default else "n").lower()
            if raw in ("y", "yes"):
                return True
            if raw in ("n", "no"):
                return False

    def ask_multiselect(self, prompt: str, entries: list[tuple[str, str]],
                        per_line: int = 3) -> list[str]:
        """Numbered multi-select; returns selected entry ids."""
        width = max(len(label) for _, label in entries) + 2
        for i, (_, label) in enumerate(entries, 1):
            if (i - 1) % per_line == 0:
                self._out("")
            self._out(f"  {i:>3}. {label:<{width}}", end="")
            if i % per_line == 0:
                self._out("")
        self._out("")
        while True:
            raw = self.ask(
                f"{prompt} — numbers, ranges (1,3-5), empty for none")
            if raw.lower() in ("none", ""):
                return []
            picked = _parse_selection(raw, len(entries))
            if picked:
                return [entries[i][0] for i in sorted(picked)]
            self._out("  nothing selected — enter numbers or leave empty")

    # ---- steps ---------------------------------------------------------

    def step_banner(self) -> None:
        self._out("=" * 62)
        self._out("  Modular Linux — netinstall edition")
        self._out("  select a system; packages download from the Arch")
        self._out("  mirrors when the install runs. nothing is preloaded.")
        self._out("=" * 62)

    def step_network(self) -> bool:
        self._out("\n[1/8] checking network connection...")
        ok, msg = self._net()
        if ok:
            self._out("  ok:", msg)
            return True
        self._out(f"  NOT REACHABLE: {msg}")
        self._out("  ethernet: plug the cable (NetworkManager is running).")
        self._out("  wi-fi: switch to another console (Alt+F2), run nmtui,")
        self._out("  connect, and return here.")
        while True:
            retry = self.ask("retry the network check? (r/abort)",
                             "r").lower()
            if retry == "r":
                ok, msg = self._net()
                if ok:
                    self._out("  ok:", msg)
                    return True
                self._out(f"  still unreachable: {msg}")
            else:
                self._out("aborted — fix networking and run modular-menu")
                return False

    def step_desktop(self) -> str:
        entries = (self.registry.by_category("desktop")
                   + self.registry.by_category("wm"))
        options = [("none", "no desktop / console only")]
        options += [(p.id, f"{p.name} ({p.category})") for p in entries]
        self._out("\n[2/8] desktop or window manager")
        for i, (_, label) in enumerate(options, 1):
            if i % 2 == 1:
                self._out("")
            self._out(f"  {i:>3}. {label:<28}", end="")
            if i % 2 == 0:
                self._out("")
        self._out("")
        while True:
            raw = self.ask("choose desktop (number)", "1")
            sel = _parse_selection(raw, len(options))
            if len(sel) == 1:
                return options[sel.pop()][0]
            self._out("  enter exactly one number")

    def step_hardware(self) -> dict[str, bool]:
        self._out("\n[3/8] hardware support")
        self._out("  (the netinstall ISO always ships ethernet + wi-fi")
        self._out("   drivers; these toggles shape the installed system)")
        defaults = {"network": True, "wifi": True, "audio": True}
        hardware: dict[str, bool] = {}
        for key, label in FEATURES:
            hardware[key] = self.ask_yes_no(f"  {label}", defaults.get(key, False))
        return hardware

    def step_roles(self) -> list[str]:
        self._out("\n[4/8] system roles (bundle applications + services)")
        profiles = self.registry.by_category("roles")
        entries = [(p.id, p.name) for p in profiles]
        return self.ask_multiselect("select roles", entries)

    def step_applications(self) -> list[str]:
        self._out("\n[5/8] applications (downloaded at install time)")
        profiles = self.registry.by_category("applications")
        entries = [(p.id, p.name) for p in profiles]
        self._out(f"  {len(entries)} applications available")
        return self.ask_multiselect("select applications", entries)

    def step_system(self) -> dict[str, str]:
        self._out("\n[6/8] system choices")
        gpu = self.ask_choice("  GPU driver", GPU_MODES, "automatic")
        filesystem = self.ask_choice("  filesystem", FILESYSTEMS, "ext4")
        bootloader = self.ask_choice("  bootloader", BOOTLOADERS,
                                     "systemd-boot")
        shell = self.ask_choice("  shell", SHELLS, "bash")
        return {"gpu": gpu, "filesystem": filesystem,
                "bootloader": bootloader, "shell": shell}

    def step_identity(self) -> dict[str, str]:
        self._out("\n[7/8] user + machine identity")
        while True:
            username = self.ask("  username")
            if USERNAME_RE.match(username):
                break
            self._out("  invalid username (lowercase letters, digits, - or _)")
        full_name = self.ask("  full name (may be empty)", "")
        while True:
            password = self._in("  user password: ")
            confirm = self._in("  confirm password: ")
            if password and password == confirm:
                break
            self._out("  passwords empty or mismatching — try again")
        root_password = ""
        if self.ask_yes_no("  set a separate root password?", False):
            while True:
                root_password = self._in("  root password: ")
                confirm = self._in("  confirm root password: ")
                if root_password and root_password == confirm:
                    break
                self._out("  passwords empty or mismatching — try again")
        while True:
            hostname = self.ask("  hostname", "modular")
            if HOSTNAME_RE.match(hostname):
                break
            self._out("  invalid hostname")
        timezone = self.ask("  timezone (e.g. Asia/Kolkata)", TIMEZONE_DEFAULT)
        return {"username": username, "full_name": full_name,
                "password": password,
                "root_password": root_password or None,
                "hostname": hostname, "timezone": timezone}

    def step_disk(self) -> Optional[str]:
        self._out("\n[8/8] target disk")
        self._out("  WARNING: the chosen disk is wiped completely.")
        devices = list_disk_devices()
        if not devices:
            self._out("  no disks found via /sys/block — install aborted.")
            return None
        for i, (path, desc) in enumerate(devices, 1):
            self._out(f"  {i}. {path:<18} {desc}")
        while True:
            raw = self.ask("disk number or /dev/ path")
            path = raw
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(devices):
                    path = devices[idx - 1][0]
                else:
                    self._out("  no such disk number")
                    continue
            elif not raw.startswith("/dev/"):
                path = f"/dev/{raw}"
            if any(d[0] == path for d in devices):
                break
            self._out(f"  {path} is not one of the listed disks")
        self._out(f"\n  everything on {path} will be DESTROYED.")
        while True:
            typed = self._in(f"  type the device name ({path}) to confirm: ")
            if typed.strip() == path:
                return path
            if typed.strip() in ("", "abort", "q"):
                self._out("aborted")
                return None
            self._out("  did not match — type it exactly, or 'abort'")

    def build_config(self, desktop: str, hardware: dict[str, bool],
                     roles: list[str], applications: list[str],
                     system: dict[str, str]) -> ModularConfiguration:
        return ModularConfiguration(
            desktop_environment=desktop,
            gpu_mode=system["gpu"],
            hardware=dict(hardware),
            roles=roles,
            applications=applications,
            shell_type=system["shell"],
            filesystem_type=system["filesystem"],
            bootloader_type=system["bootloader"],
        )

    def preview_plan(self, cfg: ModularConfiguration) -> int:
        """Resolve + count packages so the user sees what will download."""
        resolver = Resolver(self.registry)
        hardware = [k for k, v in cfg.hardware.items() if v is True
                    and k != "gpu"]
        if cfg.gpu_mode in ("nvidia", "amd", "intel"):
            hardware.append(f"gpu.{cfg.gpu_mode}")
        resolution = resolver.resolve(cfg.desktop_environment, hardware,
                                      cfg.applications, roles=cfg.roles)
        plan = build_plan(resolution, kernel=cfg.kernel,
                          filesystem=cfg.filesystem_type,
                          bootloader=cfg.bootloader_type,
                          shell=cfg.shell_type,
                          desktop_id=cfg.desktop_environment)
        n = len(plan.all_packages())
        self._out(f"\n  plan resolves to {n} packages "
                  f"(downloaded on install)")
        return n

    def run(self) -> Optional[MenuResult]:
        self.step_banner()
        if not self.step_network():
            return None
        desktop = self.step_desktop()
        hardware = self.step_hardware()
        roles = self.step_roles()
        applications = self.step_applications()
        system = self.step_system()
        identity = self.step_identity()
        device = self.step_disk()
        if device is None:
            return None

        cfg = self.build_config(desktop, hardware, roles, applications,
                                system)
        n_packages = self.preview_plan(cfg)

        cfg.save(self.config_path)
        self._out(f"  configuration saved: {self.config_path}")

        result = MenuResult(
            config=cfg, device=device,
            username=identity["username"],
            full_name=identity["full_name"],
            user_password=identity["password"],
            root_password=identity["root_password"],
            opts=InstallOptions(hostname=identity["hostname"],
                                timezone=identity["timezone"]),
            config_path=self.config_path,
            planned_packages=n_packages)

        if self.dry_run:
            self._out("dry-run: skipping install "
                      "(run `modular install "
                      f"{self.config_path}` to proceed)")
            return result

        if not self.ask_yes_no(
                f"\nstart the install onto {device} now?", False):
            self._out(f"saved — restart later with: modular install "
                      f"{self.config_path}")
            return result

        rc = run_installation(cfg, device=device,
                              username=result.username,
                              full_name=result.full_name,
                              user_password=result.user_password,
                              root_password=result.root_password,
                              opts=result.opts)
        if rc != 0:
            self._out("install failed — see the messages above")
        return result


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    menu = TextMenu()
    menu.dry_run = "--dry-run" in argv
    try:
        result = menu.run()
    except (KeyboardInterrupt, EOFError):
        print("\naborted")
        return 130
    if result is None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
