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
from engine.packages import build_plan, derive_login_manager
from engine.profiles import default_registry
from engine.resolver import Resolver
from installer.hardware.detect import detect
from installer.logging.setup import get_logger, register_secret
from installer.installation.steps import (
    bootloader_commands, enable_service_command, execute_step,
    genfstab_command, pacstrap_command, user_commands, export_configuration,
)
from installer.storage.partition import Partitioner

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
KERNELS = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
SHELLS = ["bash", "zsh", "fish"]
BOOTLOADERS = ["systemd-boot", "grub"]
FILESYSTEMS = ["ext4", "btrfs"]
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
        self._refresh_summary()

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
            radio.connect("toggled", lambda _c: self._refresh_summary())
            self.role_radio[short] = radio
            box.pack_start(radio, False, False, 2)
        custom = Gtk.RadioButton.new_with_label_from_widget(first, "Custom")
        custom.set_active(True)
        self.role_radio["custom"] = custom
        box.pack_start(custom, False, False, 2)
        note = Gtk.Label(
            label="A role pre-selects sensible defaults; everything stays "
                  "editable afterwards.", xalign=0)
        note.set_line_wrap(True)
        box.pack_start(note, False, False, 10)
        return box

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
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        labels = ["Username:", "Full name:", "Password:", "Confirm:"]
        for row, text in enumerate(labels):
            lbl = Gtk.Label(label=text)
            lbl.set_halign(Gtk.Align.END)
            grid.attach(lbl, 0, row, 1, 1)
        self.username_entry = Gtk.Entry()
        self.fullname_entry = Gtk.Entry()
        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        self.confirm_entry = Gtk.Entry()
        self.confirm_entry.set_visibility(False)
        for row, entry in enumerate((self.username_entry, self.fullname_entry,
                                     self.password_entry, self.confirm_entry)):
            grid.attach(entry, 1, row, 1, 1)
        self.admin_check = Gtk.CheckButton(label="Administrator (wheel + sudo)")
        self.admin_check.set_active(True)
        grid.attach(self.admin_check, 1, 4, 1, 1)
        return grid

    def page_disk(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        disk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        disk_box.pack_start(Gtk.Label(label="Target disk:"), False, False, 0)
        combo = Gtk.ComboBoxText()
        for dev in detect().storage:
            combo.append_text(
                f"{dev.name} ({dev.size or '?'}G) {dev.model or ''}".strip())
        devices = detect().storage
        if devices:
            combo.set_active(0)
        self.disk_combo = combo
        disk_box.pack_start(combo, True, True, 0)
        box.pack_start(disk_box, False, False, 0)
        warn = Gtk.Label()
        warn.set_markup("<span foreground='red'>"
                        "WARNING: the target disk will be erased.</span>")
        box.pack_start(warn, False, False, 10)
        return box

    def selected_device(self) -> str:
        text = self.disk_combo.get_active_text() or ""
        return "/dev/" + text.split()[0] if text else ""

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
            lines.append("")
            lines += [f"  - {p}" for p in plan.all_packages()]
            self._last_resolution = self.resolver
            self._last_plan = plan
            self._last_cfg = cfg
            self.summary_view.get_buffer().set_text("\n".join(lines))
        except Exception as exc:
            self.summary_view.get_buffer().set_text(f"error: {exc}")

    # ---- installation --------------------------------------------------
    def on_install(self, _btn):
        password = self.password_entry.get_text()
        if password != self.confirm_entry.get_text():
            self._error("Passwords do not match")
            return
        register_secret(password)
        device = self.selected_device()
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.YES_NO,
                                text=f"Erase {device or '?'} and install "
                                     "Modular Linux?")
        response = dlg.run()
        dlg.destroy()
        if response != Gtk.ResponseType.YES:
            return
        threading.Thread(target=self._install_worker, args=(password,),
                         daemon=True).start()

    def _install_worker(self, password: str):
        log = self.log
        try:
            plan = self._last_plan
            cfg = self._last_cfg
            device = self.selected_device()
            part = Partitioner(device, cfg.filesystem_type, dry_run=False)
            if part.execute(confirm=True) != 0:
                raise RuntimeError("partitioning failed")
            rc, out = execute_step(
                pacstrap_command(plan.all_packages()))
            if rc != 0:
                raise RuntimeError(f"pacstrap failed: {out}")
            execute_step(["mkdir", "-p", "/mnt/etc"])
            rc, _ = execute_step(
                ["arch-chroot", "/mnt", "/bin/bash", "-c",
                 genfstab_command()])
            username = self.username_entry.get_text() or "user"
            cmds = user_commands(username, self.fullname_entry.get_text(),
                                 password,
                                 administrator=self.admin_check.get_active())
            marker = getattr(cmds, "marker", None)
            stdin_text = None
            for i, cmd in enumerate(cmds):
                if marker and i == len(cmds) - 1:
                    u, p = marker["__stdin_password__"]
                    stdin_text = f"{u}:{p}\n"
                rc, out = execute_step(cmd, stdin_text)
                if rc != 0:
                    raise RuntimeError(f"user setup failed: {out}")
            services = set(plan.services)
            services |= {s for s, c in self.service_checks.items()
                         if c.get_active()}
            if plan.login_manager and plan.login_manager not in \
                    ("none", "ly", "cosmic-greeter"):
                services.add(plan.login_manager)
            for svc in sorted(services):
                rc, out = execute_step(enable_service_command(svc))
                if rc != 0:
                    log.warning("could not enable %s: %s", svc, out)
            for cmd in bootloader_commands(cfg.bootloader_type):
                rc, out = execute_step(cmd)
                if rc != 0:
                    raise RuntimeError("bootloader failed: " + out)
            files = export_configuration(_dump_yaml(cfg))
            for path, content in files.items():
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
            log.info("installation completed successfully on %s", device)
            GLib.idle_add(self._show_done, True, "")
        except Exception as exc:
            log.error("installation failed: %s", exc)
            GLib.idle_add(self._show_done, False, str(exc))

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
