"""GTK3 system-builder UI implementing the v1.0 flow (spec §16-§29, §42).

Pages: Welcome, Hardware, System Type, Desktop, Hardware Features,
Applications, Advanced, Services, User, Disk, Summary, Install.
"""

from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from engine.configuration import ModularConfiguration
from engine.constants import (
    SUPPORTED_BOOTLOADERS, SUPPORTED_FILESYSTEMS, SUPPORTED_KERNELS,
    SUPPORTED_SHELLS,
)
from engine.packages import build_plan, derive_login_manager
from engine.profiles import default_registry
from engine.resolver import Resolver
from installer.hardware.detect import detect
from installer.logging.setup import get_logger, register_secret
from installer.installation.steps import (
    bootloader_commands, configure_locale, enable_service_command,
    execute_step, genfstab_command, is_chroot_ready, pacstrap_command,
    regenerate_initramfs, set_hostname, set_keymap, set_timezone,
    user_commands, export_configuration,
)
from installer.storage.partition import Partitioner, is_safe_install_target

PAGES = ["Welcome", "Hardware", "System Type", "Desktop", "Features",
         "Applications", "Advanced", "Services", "User", "Disk", "Summary"]

FEATURES = [("network", "Networking"), ("wifi", "Wi-Fi"),
            ("bluetooth", "Bluetooth"), ("audio", "Audio"),
            ("webcam", "Webcam"), ("printing", "Printing"),
            ("scanner", "Scanning"), ("vpn", "VPN")]
FEATURE_GROUPS = {
    "Connectivity": ["network", "wifi", "bluetooth", "vpn"],
    "Multimedia": ["audio", "webcam"],
    "Peripherals": ["printing", "scanner"],
}
GPU_MODES = [("automatic", "Automatic"),
             ("open-source", "Open-source drivers"),
             ("nvidia-proprietary", "NVIDIA proprietary driver"),
             ("manual", "Advanced / manual")]
KERNELS = list(SUPPORTED_KERNELS)
SHELLS = list(SUPPORTED_SHELLS)
BOOTLOADERS = list(SUPPORTED_BOOTLOADERS)
FILESYSTEMS = list(SUPPORTED_FILESYSTEMS)
LOCALES = ["C.UTF-8", "en_US.UTF-8", "en_GB.UTF-8", "de_DE.UTF-8",
           "fr_FR.UTF-8", "es_ES.UTF-8", "ja_JP.UTF-8", "zh_CN.UTF-8"]
TIMEZONES = ["UTC", "Europe/Berlin", "Europe/London", "Europe/Paris",
             "America/New_York", "America/Los_Angeles", "America/Chicago",
             "Asia/Kolkata", "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"]
KEYMAPS = ["us", "gb", "de", "fr", "es", "it", "ru", "jp", "in"]
SERVICES = [("NetworkManager", True), ("bluetooth", True),
            ("pipewire", False), ("sshd", False), ("cups", False),
            ("docker", False), ("libvirtd", False), ("avahi-daemon", False)]
SOURCE_OPTIONS = [("arch", "Official Arch repositories", True),
                  ("aur", "AUR (third-party)", False),
                  ("flatpak", "Flatpak / Flathub (third-party)", False),
                  ("appimage", "AppImage (third-party)", False)]


class InstallerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Modular Linux - System Builder")
        self.set_default_size(920, 620)
        self.set_border_width(12)

        self.registry = default_registry()
        self.resolver = Resolver(self.registry)
        self.log = get_logger()
        self.hardware_info = None
        self.feature_checks: dict[str, Gtk.CheckButton] = {}
        self.app_checks: dict[str, Gtk.CheckButton] = {}
        self.service_checks: dict[str, Gtk.CheckButton] = {}
        self.source_checks: dict[str, Gtk.CheckButton] = {}
        self.desktop_radio: dict[str, Gtk.RadioButton] = {}
        self.role_radio: dict[str, Gtk.RadioButton] = {}
        self.gpu_radio: dict[str, Gtk.RadioButton] = {}
        self._last_resolution = None
        self._last_plan = None
        self._last_cfg = None
        self._building = False

        header = Gtk.HeaderBar(title="Modular Linux",
                               subtitle="Build your Arch Linux system")
        header.set_show_close_button(True)
        self.set_titlebar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add(outer)
        sidebar = Gtk.StackSidebar()
        self.stack = Gtk.Stack()
        sidebar.set_stack(self.stack)
        outer.pack_start(sidebar, False, False, 0)
        outer.pack_start(self.stack, True, True, 0)

        builders = {
            "Welcome": self.page_welcome,
            "Hardware": self.page_hardware,
            "System Type": self.page_role,
            "Desktop": self.page_desktop,
            "Features": self.page_features,
            "Applications": self.page_applications,
            "Advanced": self.page_advanced,
            "Services": self.page_services,
            "User": self.page_user,
            "Disk": self.page_disk,
            "Summary": self.page_summary,
        }
        for name in PAGES:
            self.stack.add_titled(builders[name](), name, name)
        # summary_view is created during page_summary construction; refresh
        # only after the stack is fully built to avoid the old race.
        GLib.idle_add(self._refresh_summary)

    # ---- pages -------------------------------------------------------
    def page_welcome(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>"
                         "MODULAR LINUX</span>")
        body = Gtk.Label(
            label="Build your Arch Linux system.\n\n"
                  "Choose a role, desktop, hardware support and applications.\n"
                  "Only what you select will be installed.")
        body.set_justify(Gtk.Justification.CENTER)
        start = Gtk.Button(label="Start")
        start.connect("clicked", lambda _b: self.stack.set_visible_child_name(
            "Hardware"))
        box.pack_start(title, False, False, 30)
        box.pack_start(body, False, False, 0)
        box.pack_start(start, False, False, 20)
        return box

    def page_hardware(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        refresh = Gtk.Button(label="Detect Hardware")
        refresh.connect("clicked", self.on_detect_hardware)
        self.hardware_view = Gtk.TextView()
        self.hardware_view.set_editable(False)
        self.hardware_view.set_monospace(True)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.hardware_view)
        box.pack_start(refresh, False, False, 0)
        box.pack_start(scroll, True, True, 0)
        return box

    def on_detect_hardware(self, _btn):
        self.hardware_info = detect()

        def render():
            info = self.hardware_info
            lines = [f"CPU      : {info.cpu.model} ({info.cpu.cores} cores)",
                     f"Memory   : {info.memory.total_mb} MB",
                     f"GPU      : {', '.join(info.gpu.vendors) or 'unknown'}"]
            lines += [f"Storage  : {d.name} {d.size or ''} {d.model or ''}"
                      for d in info.storage]
            lines += [f"Ethernet : {'yes' if info.ethernet else 'no'}",
                      f"Wi-Fi    : {'yes' if info.wifi else 'no'}",
                      f"Bluetooth: {'yes' if info.bluetooth else 'no'}",
                      f"Audio    : {'yes' if info.audio else 'no'}",
                      f"Webcam   : {'yes' if info.webcam else 'no'}"]
            self.hardware_view.get_buffer().set_text("\n".join(lines))
            for key, active in (("wifi", info.wifi),
                                ("bluetooth", info.bluetooth),
                                ("audio", info.audio)):
                if key in self.feature_checks:
                    self.feature_checks[key].set_active(active)
            self._refresh_summary()
        render()

    def page_role(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        label = Gtk.Label(label="What are you building?", xalign=0)
        box.pack_start(label, False, False, 4)
        first = None
        for profile in self.registry.by_category("roles"):
            short = profile.id.removeprefix("role.")
            radio = Gtk.RadioButton.new_with_label_from_widget(
                first, profile.name)
            radio.get_child().set_tooltip_text(profile.description)
            if first is None:
                first = radio
            radio.connect("toggled", self.on_role_toggled)
            self.role_radio[short] = radio
            box.pack_start(radio, False, False, 2)
        custom = Gtk.RadioButton.new_with_label_from_widget(first, "Custom")
        custom.set_active(True)
        custom.connect("toggled", self.on_role_toggled)
        self.role_radio["custom"] = custom
        box.pack_start(custom, False, False, 2)
        note = Gtk.Label(
            label="A role pre-selects sensible defaults; everything stays "
                  "editable afterwards.", xalign=0)
        note.set_line_wrap(True)
        box.pack_start(note, False, False, 10)
        return box

    def on_role_toggled(self, _radio):
        self.apply_roles_defaults()
        self._refresh_summary()

    def selected_roles(self) -> list[str]:
        return [k for k, r in self.role_radio.items() if r.get_active()
                and k != "custom"]

    def page_desktop(self):
        scroller = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        def add_heading(text):
            h = Gtk.Label(xalign=0)
            h.set_markup(f"<b>{text}</b>")
            box.pack_start(h, False, False, 8)

        def add_radio(key, label, group=None):
            radio = Gtk.RadioButton.new_with_label_from_widget(group, label)
            radio.connect("toggled", lambda _c: self._refresh_summary())
            self.desktop_radio[key] = radio
            box.pack_start(radio, False, False, 2)
            return radio

        add_heading("Desktop Environments")
        first = None
        for p in self.registry.by_category("desktop"):
            first = add_radio(p.id, p.name, first)
        add_heading("Window Managers / Compositors")
        wm_first = None
        for p in self.registry.by_category("wm"):
            wm_first = add_radio(p.id, p.name, wm_first or first)
        none_radio = add_radio("none", "No desktop", wm_first or first)
        none_radio.set_active(True)
        scroller.add(box)
        return scroller

    def selected_desktop(self) -> str:
        for key, radio in self.desktop_radio.items():
            if radio.get_active():
                return key
        return "none"

    def page_features(self):
        outer = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        def heading(text):
            h = Gtk.Label(text, xalign=0)
            h.set_markup(f"<b>{text}</b>")
            box.pack_start(h, False, False, 8)

        def check(key, label):
            c = Gtk.CheckButton(label=label)
            c.connect("toggled", lambda _b: self._refresh_summary())
            self.feature_checks[key] = c
            box.pack_start(c, False, False, 2)

        heading("Connectivity")
        for key in FEATURE_GROUPS["Connectivity"]:
            check(key, dict(FEATURES)[key])
        heading("Multimedia")
        for key in FEATURE_GROUPS["Multimedia"]:
            check(key, dict(FEATURES)[key])
        heading("Peripherals")
        for key in FEATURE_GROUPS["Peripherals"]:
            check(key, dict(FEATURES)[key])
        heading("GPU")
        first = None
        for mode, label in GPU_MODES:
            r = Gtk.RadioButton.new_with_label_from_widget(first, label)
            if first is None:
                first = r
                r.set_active(True)
            r.connect("toggled", lambda _c: self._refresh_summary())
            self.gpu_radio[mode] = r
            box.pack_start(r, False, False, 2)
        outer.add(box)
        return outer

    def selected_gpu_mode(self) -> str:
        for mode, radio in self.gpu_radio.items():
            if radio.get_active():
                return mode
        return "automatic"

    def page_applications(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        search = Gtk.SearchEntry()
        search.set_placeholder_text("Search applications...")
        search.connect("search-changed", self.on_app_search)
        vbox.pack_start(search, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        self.apps_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                 spacing=2)
        by_cat: dict[str, list] = {}
        for profile in self.registry.by_category("applications"):
            by_cat.setdefault(profile.category, []).append(profile)
        for cat in sorted(by_cat):
            h = Gtk.Label(xalign=0)
            h.set_markup(f"<b>{cat.title()}</b>")
            self.apps_list.pack_start(h, False, False, 8)
            for profile in by_cat[cat]:
                short = profile.id.removeprefix("app.")
                src_tag = {"aur": " [AUR]", "flatpak": " [Flatpak]",
                           "appimage": " [AppImage]"}.get(profile.source or "",
                                                          "")
                row = Gtk.CheckButton(
                    label=f"{profile.name}{src_tag}")
                row.get_child().set_tooltip_text(profile.description or short)
                row._modular_id = short
                row._modular_cat = cat
                row.connect("toggled", lambda _c: self._refresh_summary())
                self.app_checks[short] = row
                self.apps_list.pack_start(row, False, False, 2)
        scroller.add(self.apps_list)
        vbox.pack_start(scroller, True, True, 0)
        return vbox

    def on_app_search(self, entry):
        query = entry.get_text().lower()
        for child in self.apps_list.get_children():
            if isinstance(child, Gtk.Label):
                continue
            visible = not query or getattr(child, "_modular_cat",
                                           "").startswith(query)
            if hasattr(child, "_modular_id"):
                prof = self.app_checks[getattr(child, "_modular_id")]
                name = prof.get_label().lower() if prof else ""
                visible = not query or query in name or \
                    getattr(child, "_modular_cat", "").lower().startswith(query)
            child.set_visible(visible)

    def page_advanced(self):
        grid = Gtk.Grid(column_spacing=24, row_spacing=6)

        def section(col, title):
            lbl = Gtk.Label(xalign=0)
            lbl.set_markup(f"<b>{title}</b>")
            grid.attach(lbl, col, 0, 1, 1)

        def radio_group(col, options, active_index, store, start_row=1):
            first = None
            for i, opt in enumerate(options):
                r = Gtk.RadioButton.new_with_label_from_widget(first, opt)
                if first is None:
                    first = r
                    r.set_active(i == active_index)
                store.append((opt, r))
                grid.attach(r, col, start_row + i, 1, 1)

        section(0, "Kernel")
        self.kernel_radios: list[tuple[str, Gtk.RadioButton]] = []
        radio_group(0, KERNELS, 0, self.kernel_radios)
        section(1, "Shell")
        self.shell_radios: list[tuple[str, Gtk.RadioButton]] = []
        radio_group(1, SHELLS, 0, self.shell_radios)
        section(2, "Filesystem")
        self.fs_radios: list[tuple[str, Gtk.RadioButton]] = []
        radio_group(2, FILESYSTEMS, 0, self.fs_radios)
        section(3, "Bootloader")
        self.bl_radios: list[tuple[str, Gtk.RadioButton]] = []
        radio_group(3, BOOTLOADERS, 0, self.bl_radios)

        row = max(len(KERNELS), len(SHELLS)) + 2
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup("<b>Package Sources</b>")
        grid.attach(lbl, 0, row, 4, 1)
        for i, (key, label, default) in enumerate(SOURCE_OPTIONS):
            c = Gtk.CheckButton(label=label)
            c.set_active(default)
            c.set_sensitive(key != "arch")
            c.connect("toggled", lambda _c: self._refresh_summary())
            self.source_checks[key] = c
            grid.attach(c, 0, row + 1 + i, 3, 1)
        warn = Gtk.Label(xalign=0)
        warn.set_markup("<span foreground='#c0392b'>"
                        "Third-party sources install untrusted software and "
                        "are never enabled silently.</span>")
        grid.attach(warn, 0, row + 5, 4, 1)
        return grid

    def _radio_value(self, store) -> str:
        for value, radio in store:
            if radio.get_active():
                return value
        return ""

    def page_services(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        note = Gtk.Label(
            label="Only services that are required or explicitly selected "
                  "are enabled.", xalign=0)
        box.pack_start(note, False, False, 6)
        for svc, default in SERVICES:
            c = Gtk.CheckButton(label=svc)
            c.set_active(default)
            self.service_checks[svc] = c
            box.pack_start(c, False, False, 2)
        return box

    def page_user(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll = Gtk.ScrolledWindow()
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        scroll.add(grid)
        outer.pack_start(scroll, True, True, 0)

        def label(text, row):
            lbl = Gtk.Label(label=text)
            lbl.set_halign(Gtk.Align.END)
            grid.attach(lbl, 0, row, 1, 1)

        def entry(row, password=False, placeholder=""):
            e = Gtk.Entry()
            if password:
                e.set_visibility(False)
            if placeholder:
                e.set_placeholder_text(placeholder)
            grid.attach(e, 1, row, 1, 1)
            return e

        label("Hostname:", 0)
        self.hostname_entry = entry(0, placeholder="modular")

        label("Locale:", 1)
        self.locale_combo = Gtk.ComboBoxText()
        for loc in LOCALES:
            self.locale_combo.append_text(loc)
        self.locale_combo.set_active(0)
        grid.attach(self.locale_combo, 1, 1, 1, 1)

        label("Timezone:", 2)
        self.timezone_combo = Gtk.ComboBoxText()
        for tz in TIMEZONES:
            self.timezone_combo.append_text(tz)
        self.timezone_combo.set_active(0)
        grid.attach(self.timezone_combo, 1, 2, 1, 1)

        label("Keymap:", 3)
        self.keymap_combo = Gtk.ComboBoxText()
        for km in KEYMAPS:
            self.keymap_combo.append_text(km)
        self.keymap_combo.set_active(0)
        grid.attach(self.keymap_combo, 1, 3, 1, 1)

        sep1 = Gtk.Separator()
        grid.attach(sep1, 0, 4, 2, 1)

        label("Username:", 5)
        self.username_entry = entry(5, placeholder="user")
        label("Full name:", 6)
        self.fullname_entry = entry(6, placeholder="User")
        label("User password:", 7)
        self.password_entry = entry(7, password=True)
        label("Confirm:", 8)
        self.confirm_entry = entry(8, password=True)

        label("Root password:", 9)
        self.root_password_entry = entry(9, password=True)
        label("(optional)", 9)

        self.admin_check = Gtk.CheckButton(label="Administrator (wheel + sudo)")
        self.admin_check.set_active(True)
        grid.attach(self.admin_check, 1, 10, 1, 1)

        for w in (self.hostname_entry, self.fullname_entry,
                  self.username_entry):
            w.connect("changed", lambda _e: self._refresh_summary())
        return outer

    def page_disk(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        disk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        disk_box.pack_start(Gtk.Label(label="Target disk:"), False, False, 0)
        combo = Gtk.ComboBoxText()
        all_devices = detect().storage
        safe = [d for d in all_devices if is_safe_install_target(d)]
        if not safe:
            err = Gtk.Label()
            err.set_markup("<span foreground='red'>"
                           "No suitable install target found. "
                           "Connect a disk of at least 8 GB and press "
                           "Detect Hardware again.</span>")
            err.set_line_wrap(True)
            box.pack_start(err, False, False, 4)
        for dev in safe:
            combo.append_text(
                f"/dev/{dev.name} ({dev.size or '?'}G) "
                f"{dev.model or ''}".strip())
        if safe:
            combo.set_active(0)
        self.disk_combo = combo
        self._disk_devices = safe
        disk_box.pack_start(combo, True, True, 0)
        box.pack_start(disk_box, False, False, 0)
        warn = Gtk.Label()
        warn.set_markup("<span foreground='red'>"
                        "WARNING: the target disk will be erased.</span>")
        box.pack_start(warn, False, False, 10)
        return box

    def selected_device(self) -> str:
        text = self.disk_combo.get_active_text() or ""
        return text.split()[0] if text else ""

    def page_summary(self):
        scroller = Gtk.ScrolledWindow()
        self.summary_view = Gtk.TextView()
        self.summary_view.set_editable(False)
        self.summary_view.set_monospace(True)
        scroller.add(self.summary_view)
        button = Gtk.Button(label="Install")
        button.get_style_context().add_class("destructive-action")
        button.connect("clicked", self.on_install)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.pack_start(scroller, True, True, 0)
        vbox.pack_start(button, False, False, 0)
        return vbox

    # ---- selection plumbing ------------------------------------------
    def current_selection(self) -> dict:
        hardware = [k for k, c in self.feature_checks.items()
                    if c.get_active()]
        gpu_mode = self.selected_gpu_mode()
        apps = [k for k, c in self.app_checks.items() if c.get_active()]
        roles = self.selected_roles()
        sources = {k: c.get_active() for k, c in self.source_checks.items()}
        services = [s for s, c in self.service_checks.items()
                    if c.get_active()]
        kernel = self._radio_value(self.kernel_radios) or "linux"
        shell = self._radio_value(self.shell_radios) or "bash"
        fs = self._radio_value(self.fs_radios) or "ext4"
        bl = self._radio_value(self.bl_radios) or "systemd-boot"
        desktop = self.selected_desktop()
        return {"desktop": desktop, "hardware": hardware, "gpu": gpu_mode,
                "applications": apps, "roles": roles, "sources": sources,
                "services": services, "kernel": kernel, "shell": shell,
                "filesystem": fs, "bootloader": bl}

    def apply_roles_defaults(self):
        """Populate defaults from the chosen role (spec §18)."""
        role_id = None
        for short, radio in self.role_radio.items():
            if radio.get_active() and short != "custom":
                role_id = f"role.{short}"
        if not role_id:
            return
        profile = self.registry.get(role_id)
        for req in profile.requires:
            if req.startswith("hardware."):
                key = req.removeprefix("hardware.")
                if key in self.feature_checks:
                    self.feature_checks[key].set_active(True)
            elif req.startswith("app."):
                key = req.removeprefix("app.")
                if key in self.app_checks:
                    self.app_checks[key].set_active(True)

    def build_configuration(self) -> tuple[ModularConfiguration, object]:
        sel = self.current_selection()
        hardware_flags = {f: (f in sel["hardware"]) for f, _ in FEATURES}
        cfg = ModularConfiguration(
            kernel=sel["kernel"],
            desktop_environment=("none" if sel["desktop"] == "none"
                                 else sel["desktop"]),
            display="automatic",
            gpu_mode=sel["gpu"],
            hardware=hardware_flags | {"gpu": sel["gpu"]},
            roles=sel["roles"],
            applications=sel["applications"],
            shell_type=sel["shell"],
            filesystem_type=sel["filesystem"],
            bootloader_type=sel["bootloader"],
            sources={**{"arch": True, "aur": False, "flatpak": False,
                        "appimage": False}, **sel["sources"]},
        )
        extra_hw = list(sel["hardware"])
        gpu_vendor = self._gpu_vendor_profile(sel["gpu"])
        if gpu_vendor:
            extra_hw.append(gpu_vendor)
        resolution = self.resolver.resolve(cfg.desktop_environment,
                                           extra_hw, cfg.applications,
                                           roles=cfg.roles)
        plan = build_plan(resolution, kernel=cfg.kernel,
                          filesystem=cfg.filesystem_type,
                          bootloader=cfg.bootloader_type,
                          shell=cfg.shell_type,
                          desktop_id=cfg.desktop_environment,
                          login_manager=None,
                          roles=cfg.roles, hardware=extra_hw,
                          sources=cfg.sources)
        return cfg, plan

    def _gpu_vendor_profile(self, mode: str) -> str | None:
        vendors = set()
        if self.hardware_info:
            vendors = set(self.hardware_info.gpu.vendors)
        if mode == "nvidia-proprietary":
            return "gpu.nvidia"
        if "nvidia" in vendors:
            return "gpu.nouveau" if mode == "open-source" else "gpu.nvidia"
        for v in ("amd", "intel"):
            if v in vendors:
                return f"gpu.{v}"
        if mode == "open-source":
            return "gpu.intel"
        return None

    def _refresh_summary(self, *_args):
        if not hasattr(self, "summary_view") or \
                not hasattr(self, "kernel_radios"):
            return
        try:
            cfg, plan = self.build_configuration()
            lines = ["Installation Summary", ""]
            lines.append(f"Base       : Arch Linux ({cfg.architecture})")
            lines.append(f"Role       : {', '.join(cfg.roles) or 'Custom'}")
            lines.append(f"Desktop    : {cfg.desktop_environment}")
            lines.append(f"Kernel     : {cfg.kernel}")
            lines.append(f"Display    : {plan.display or 'automatic'}")
            lines.append(f"Login Mgr  : {plan.login_manager or 'none'}")
            hw = ", ".join(sorted(k for k, v in cfg.hardware.items()
                                  if v is True))
            lines.append(f"Hardware   : {hw or '-'}")
            lines.append(f"GPU        : {cfg.gpu_mode}")
            lines.append(f"Apps       : {len(cfg.applications)} selected")
            src = ", ".join(k for k, v in cfg.sources.items() if v)
            third = " (+ third-party!)" if (cfg.sources.get("aur")
                                            or cfg.sources.get("flatpak")) \
                else ""
            lines.append(f"Sources    : {src}{third}")
            lines.append(f"Shell      : {cfg.shell_type}")
            lines.append(f"Filesystem : {cfg.filesystem_type}")
            lines.append(f"Bootloader : {cfg.bootloader_type}")
            lines.append(f"Hostname   : {self._hostname_or_default()}")
            lines.append(f"Locale     : {self._locale_or_default()}")
            lines.append(f"Timezone   : {self._timezone_or_default()}")
            lines.append(f"Keymap     : {self._keymap_or_default()}")
            lines.append("")
            lines += [f"  - {p}" for p in plan.all_packages()]
            self._last_resolution = self.resolver
            self._last_plan = plan
            self._last_cfg = cfg
            self.summary_view.get_buffer().set_text("\n".join(lines))
        except Exception as exc:
            self.summary_view.get_buffer().set_text(f"error: {exc}")

    def _hostname_or_default(self) -> str:
        if hasattr(self, "hostname_entry"):
            v = self.hostname_entry.get_text().strip()
            if v:
                return v
        return "modular"

    def _locale_or_default(self) -> str:
        if hasattr(self, "locale_combo"):
            return self.locale_combo.get_active_text() or LOCALES[0]
        return LOCALES[0]

    def _timezone_or_default(self) -> str:
        if hasattr(self, "timezone_combo"):
            return self.timezone_combo.get_active_text() or TIMEZONES[0]
        return TIMEZONES[0]

    def _keymap_or_default(self) -> str:
        if hasattr(self, "keymap_combo"):
            return self.keymap_combo.get_active_text() or KEYMAPS[0]
        return KEYMAPS[0]

    # ---- installation --------------------------------------------------
    def on_install(self, _btn):
        password = self.password_entry.get_text()
        if password != self.confirm_entry.get_text():
            self._error("User passwords do not match")
            return
        root_pw = self.root_password_entry.get_text() or ""
        confirm_root = getattr(self, "root_confirm_entry", None)
        if confirm_root is not None and root_pw != confirm_root.get_text():
            self._error("Root passwords do not match")
            return
        register_secret(password)
        if root_pw:
            register_secret(root_pw)
        if self._building:
            self._error("An installation is already in progress")
            return
        device = self.selected_device()
        if not device:
            self._error("No target disk selected")
            return
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.YES_NO,
                                text=f"Erase {device} and install "
                                     "Modular Linux?")
        response = dlg.run()
        dlg.destroy()
        if response != Gtk.ResponseType.YES:
            return
        self._building = True
        threading.Thread(target=self._install_worker,
                         args=(password, root_pw), daemon=True).start()

    def _run_steps(self, log, steps, label, allow_continue=True):
        for cmd in steps:
            rc, out = execute_step(cmd, timeout=300)
            if rc != 0:
                msg = f"{label} failed: {out}"
                if allow_continue:
                    log.warning(msg)
                else:
                    raise RuntimeError(msg)
            else:
                log.info("%s ok: %s", label, " ".join(cmd[:3]))

    def _install_worker(self, password: str, root_password: str):
        log = self.log
        mounted = False
        try:
            plan = self._last_plan
            cfg = self._last_cfg
            device = self.selected_device()
            part = Partitioner(device, cfg.filesystem_type, dry_run=False)
            if part.execute(confirm=True) != 0:
                raise RuntimeError("partitioning failed")
            mounted = True
            rc, out = execute_step(
                pacstrap_command(plan.all_packages()), timeout=1800)
            if rc != 0:
                raise RuntimeError(f"pacstrap failed: {out}")
            if not is_chroot_ready("/mnt"):
                raise RuntimeError("pacstrap did not populate /mnt")
            execute_step(["mkdir", "-p", "/mnt/etc"], timeout=30)
            rc, _ = execute_step(
                ["arch-chroot", "/mnt", "/bin/bash", "-c",
                 genfstab_command()], timeout=60)
            if rc != 0:
                raise RuntimeError("genfstab failed")
            hostname = self._hostname_or_default()
            for cmd in set_hostname(hostname):
                rc, out = execute_step(cmd, timeout=30)
                if rc != 0:
                    raise RuntimeError(f"hostname setup failed: {out}")
            for cmd in set_timezone(self._timezone_or_default()):
                rc, out = execute_step(cmd, timeout=30)
                if rc != 0:
                    raise RuntimeError(f"timezone setup failed: {out}")
            for cmd in set_keymap(self._keymap_or_default()):
                rc, out = execute_step(cmd, timeout=30)
                if rc != 0:
                    raise RuntimeError(f"keymap setup failed: {out}")
            for cmd in configure_locale(self._locale_or_default()):
                rc, out = execute_step(cmd, timeout=120)
                if rc != 0:
                    raise RuntimeError(f"locale setup failed: {out}")
            username = self.username_entry.get_text().strip() or "user"
            fullname = self.fullname_entry.get_text().strip() or username
            cmds = user_commands(username, fullname, password,
                                 root_password=root_password or None,
                                 administrator=self.admin_check.get_active())
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
                    raise RuntimeError(f"user setup failed: {out}")
            for cmd in regenerate_initramfs(cfg.kernel):
                rc, out = execute_step(cmd, timeout=300)
                if rc != 0:
                    raise RuntimeError(f"initramfs regen failed: {out}")
            services = set(plan.services)
            services |= {s for s, c in self.service_checks.items()
                         if c.get_active()}
            if plan.login_manager and plan.login_manager not in \
                    ("none", "ly", "cosmic-greeter"):
                services.add(plan.login_manager)
            for svc in sorted(services):
                rc, out = execute_step(enable_service_command(svc),
                                       timeout=60)
                if rc != 0:
                    log.warning("could not enable %s: %s", svc, out)
            for cmd in bootloader_commands(cfg.bootloader_type):
                rc, out = execute_step(cmd, timeout=300)
                if rc != 0:
                    raise RuntimeError("bootloader failed: " + out)
            files = export_configuration(_dump_yaml(cfg))
            execute_step(["mkdir", "-p", "/mnt/etc/modular"], timeout=30)
            for path, content in files.items():
                execute_step(["tee", path], stdin_text=content, timeout=30)
            log.info("installation completed successfully on %s", device)
            GLib.idle_add(self._show_done, True, "")
        except Exception as exc:
            log.error("installation failed: %s", exc)
            # Best-effort cleanup: umount what we may have mounted so the
            # next attempt starts from a clean state.
            if mounted:
                for target in ("/mnt/boot/efi", "/mnt"):
                    try:
                        execute_step(["umount", "-R", target], timeout=15)
                    except Exception:
                        pass
            GLib.idle_add(self._show_done, False, str(exc))
        finally:
            self._building = False

    def _show_done(self, ok: bool, message: str):
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=(Gtk.MessageType.INFO if ok
                                              else Gtk.MessageType.ERROR),
                                buttons=Gtk.ButtonsType.CLOSE,
                                text=("Installation complete. Reboot to use "
                                      "your system." if ok else
                                      f"Installation failed: {message}"))
        dlg.run()
        dlg.destroy()
        return False

    def _error(self, message: str):
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.CLOSE, text=message)
        dlg.run()
        dlg.destroy()


def _dump_yaml(cfg: ModularConfiguration) -> str:
    import io

    buf = io.StringIO()
    try:
        import yaml
        yaml.safe_dump(cfg.to_dict(), buf, sort_keys=False)
        return buf.getvalue()
    except ImportError:
        return repr(cfg.to_dict())
