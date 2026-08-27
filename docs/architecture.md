# Architecture

Modular Linux is a **composition and installation layer** on top of an
existing distribution. v1.0 targets Arch Linux (spec §57-§58).

## Component Map

| Spec section | Implementation |
|---|---|
| §16-§29 Installer UI | `installer/main.py`, `installer/ui/app.py` (12-page workflow) |
| §5/§37 Hardware detection | `hardware/modular-detect.c` + `installer/hardware/detect.py` |
| §6/§7 Desktops & WMs | `profiles/desktop/*.yaml`, `profiles/wm/*.yaml` |
| §9 Hardware features | `profiles/hardware/*.yaml` |
| §10 GPU profiles | `profiles/gpu/{intel,amd,nvidia,nouveau}.yaml` + auto-detection glue |
| §15 Roles | `profiles/roles/*.yaml` |
| §11-§13 Applications & sources | `profiles/applications/*.yaml` (`source:` field) |
| §23 Kernel/shell/bootloader | config `system.kernel`, `shell.type`, advanced page |
| §32 Dependency resolution | `engine/resolver.py` + `cmd/modular/resolver.go` (identical semantics) |
| §34/§35 Installation engine | UI -> Configuration -> Resolver -> Plan -> Executor split |
| §36 Arch installation | pacstrap/arch-chroot/genfstab via `installer/installation/steps.py` |
| §30 Configuration export | `engine/configuration.py` -> `/etc/modular/modular.yaml` |
| §38 Build system | root `build.sh` -> `dist/modular-linux-arch-x86_64.iso` |
| §41 VM testing | `scripts/test-vm.sh` (QEMU/KVM UEFI) |
| §48 Trust model | `sources:` block; AUR/Flatpak require explicit opt-in, validated |
| §50 Logs | `/var/log/modular/installer.log` with secret redaction |
| §52 Future backends | engine is distro-agnostic; only `profiles/` and executor are Arch-specific |

## Language Policy (spec §47)

- **Bash** — ISO build + orchestration of upstream tools (archiso, pacstrap,
  sfdisk, bootctl). Never reimplements packaging/partitioning.
- **Python** — installer logic, configuration, GUI (PyGObject/GTK3).
- **Go** — `bin/modular`: single static CLI binary for dev/testing.
- **C** — `bin/modular-detect`: zero-dependency sysfs prober emitting JSON.

## Data Flow (spec §57)

```text
profiles/*.yaml ─┐
selection ───────┼─> Resolver -> InstallationPlan -> pacstrap/systemd/bootloader
modular.yaml ────┘                                                  │
                                                                    v
                                                   /etc/modular/modular.yaml
```

Resolver pipeline (§32): selected profiles -> dependencies -> package graph
-> conflict detection -> deduplication -> service resolution -> plan.

## Safety Model

1. Plan generated and validated **before** disk modification (§51).
2. Partitioner refuses to run without explicit confirmation parameters.
3. Passwords travel only via stdin to chpasswd; redacted from logs; never in
   argv or config files (§48).
4. Third-party sources never enabled invisibly (§48).

