# Modular Linux

**Modular Linux is an Arch-based modular Linux system builder, not a
replacement distribution.** It provides a bootable ISO and a graphical
system builder that installs only what the user selects: hardware support,
desktop environments or window managers, applications, development
environments, services, and system roles.

> Build the Linux system the user actually wants instead of installing a
> generic system and removing everything they do not want.

## Repository Layout

```text
modular-linux/
├── build.sh            one-command ISO build -> dist/modular-linux-arch-x86_64.iso
├── Makefile            builds bin/ (C hardware prober + Go CLI)
├── iso/                archiso profile (live environment)
├── installer/          Python + GTK3 graphical installer
├── engine/             profile engine, resolver, validation (Python)
├── cli/                Python CLI fallback (python -m cli)
├── cmd/modular/        Go CLI -> bin/modular (static binary)
├── hardware/           C sysfs prober -> bin/modular-detect (JSON out)
├── profiles/           YAML catalog: desktops, WMs, GPU, roles, apps
├── schema/             modular.schema.yaml (v1 config schema)
├── examples/           shareable modular.yaml configs
├── scripts/            setup-dev.sh, build-iso.sh, test-vm.sh, validators
└── tests/              pytest suites (engine/hardware/installation/profiles)
```

## Quick Start

```bash
# one-time dev setup (Arch/EndeavourOS): toolchains + venv + tests
scripts/setup-dev.sh

source .venv/bin/activate

./bin/modular list roles                 # general/developer/gaming/server/...
./bin/modular list desktops              # 9 DEs + 7 window managers
./bin/modular resolve kde firefox audio  # resolution demo
python -m cli generate-plan examples/developer-workstation.yaml

# graphical system builder (needs a display; Xvfb works headless)
python installer/main.py
```

## Configuration Example (v1)

```yaml
version: 1
base: {distribution: arch}
system: {architecture: x86_64, kernel: linux, init: systemd}
desktop: {environment: kde}
hardware: {network: true, wifi: true, bluetooth: true, audio: true,
           webcam: true, gpu: automatic}
roles: [developer]
applications: [firefox, git]
shell: {type: bash}
filesystem: {type: ext4}
bootloader: {type: systemd-boot}
sources: {arch: true, aur: false, flatpak: false, appimage: false}
```

After installation the system exports its configuration to
`/etc/modular/modular.yaml` — the primary representation of the installed
system and a portable recipe for reproducing it elsewhere.

## Building the ISO

```bash
./build.sh               # dist/modular-linux-arch-x86_64.iso
./build.sh --clean       # wipe work dirs + dist first
./build.sh --debug       # verbose mkarchiso
./build.sh --test        # build then boot in QEMU/KVM (UEFI)
```

Requires `archiso`, `qemu-desktop` and `edk2-ovmf` (installed by
`scripts/setup-dev.sh`).

## Trust Model

Package sources are explicit. Official Arch repositories are trusted;
AUR, Flatpak and AppImage sources are third-party, must be enabled
explicitly in the UI or configuration, and are flagged in the plan.

See `docs/architecture.md` for the component map and language policy.
