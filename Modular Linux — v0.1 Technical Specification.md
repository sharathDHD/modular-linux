# Modular Linux — v0.1 Technical Specification

**Project:** Modular Linux  
**Version:** 0.1  
**Status:** Initial Development Specification  
**Target Base:** Arch Linux  
**Architecture:** x86_64 / UEFI  
**Primary Goal:** Build a minimal, modular Linux installation system that allows users to construct an operating system from a base system, hardware capabilities, desktop environments, and application profiles.

---

## 1. Project Overview

Modular Linux is a configurable Linux installation platform designed around the principle of **installing only what the user selects and requires**.

Traditional Linux distributions generally provide a predefined collection of software and system components. Modular Linux instead provides a minimal bootable environment and allows the user to construct the target installation during setup.

For version 0.1, Arch Linux will be used as the sole base distribution.

The system will provide:

1. A bootable ISO.
2. A minimal live environment.
3. Hardware detection.
4. A graphical installation interface.
5. Modular feature selection.
6. Desktop environment selection.
7. Application selection.
8. Dependency resolution.
9. Automated Arch installation.
10. User account creation.
11. Bootloader configuration.
12. System configuration export.

---

# 2. Goals

## 2.1 Primary Goals

Version 0.1 must allow a user to:

- Boot Modular Linux from USB.
- Detect their hardware automatically.
- Select required hardware functionality.
- Select a desktop environment or no desktop.
- Select applications.
- Configure a user account.
- Select an installation disk.
- Install a minimal Arch-based system.
- Boot into the resulting system.
- Export the resulting configuration.

---

## 2.2 Design Principles

The project should follow these principles:

### Minimal by default

No unnecessary desktop environments, applications, or services should be installed.

### Modular

Components should be independently selectable.

### Configuration-driven

The system should be defined by configuration rather than hard-coded installer logic.

### Reproducible

A configuration generated on one system should be usable to recreate the same configuration on another system.

### Hardware-aware

The installer should detect available hardware and install only relevant components.

### Upstream-oriented

Existing Linux technologies should be used wherever possible instead of creating replacements.

### Distribution-neutral architecture

Although v0.1 uses Arch Linux, the internal architecture should not permanently depend on Arch-specific concepts.

---

# 3. v0.1 Scope

## 3.1 Included

| Component | v0.1 |
|---|---|
| Arch Linux base | Required |
| Archiso | Required |
| UEFI | Required |
| x86_64 | Required |
| Hardware detection | Required |
| Networking | Required |
| Wi-Fi | Required |
| Bluetooth | Required |
| Audio | Required |
| Webcam | Required |
| GPU detection | Required |
| KDE Plasma | Supported |
| GNOME | Supported |
| XFCE | Supported |
| Hyprland | Supported |
| No desktop | Supported |
| Application profiles | Supported |
| Dependency resolution | Supported |
| User creation | Supported |
| ext4 | Supported |
| Btrfs | Optional/experimental |
| systemd-boot | Supported |
| Configuration export | Supported |
| Offline installation | Not required |
| Automatic dual boot | Not required |
| Multiple distributions | Not required |

---

# 4. Explicitly Out of Scope

The following features must not be required for v0.1:

- Debian support
- Ubuntu support
- Fedora support
- BlackArch integration
- Custom package manager
- Custom Linux kernel
- Custom desktop environment
- Automatic dual-boot configuration
- ARM support
- Custom package repository
- Web-based OS builder
- App store
- Cloud synchronization
- AI assistant
- Automatic Secure Boot signing
- Large application catalog
- Automatic driver compilation
- Gaming optimization framework

These features may be considered in future releases.

---

# 5. High-Level Architecture

```text
                         Modular Linux ISO
                                │
                                ▼
                       Minimal Live System
                                │
                                ▼
                       Hardware Detection
                                │
                                ▼
                         Installer UI
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
       Base System          Hardware Features       Desktop
          │                     │                     │
        Arch              ┌─────┼─────┐         ┌─────┼─────┐
                          │     │     │         │     │     │
                        WiFi  Audio Webcam     KDE  GNOME XFCE
                          │     │     │
                          └─────┼─────┘
                                │
                                ▼
                         Applications
                                │
                                ▼
                       Dependency Resolver
                                │
                                ▼
                         Package Manager
                                │
                                ▼
                         Target Filesystem
                                │
                                ▼
                          Bootloader
                                │
                                ▼
                         Installed System
                                │
                                ▼
                        modular.yaml
```

---

# 6. Technology Stack

## 6.1 Base Distribution

**Arch Linux**

Arch provides:

- Minimal base system
- Rolling packages
- pacman
- official repositories
- extensive hardware support
- Archiso
- flexible installation

---

## 6.2 ISO Builder

**Archiso**

Archiso will be used to create the bootable installation environment.

Responsibilities:

- Create live ISO
- Include installer
- Include hardware detection utilities
- Include profile definitions
- Include networking components
- Boot through UEFI

---

## 6.3 Installer

Initial implementation:

**Python + GTK**

Responsibilities:

- UI
- configuration collection
- hardware presentation
- disk selection
- installation orchestration
- error reporting
- configuration generation

---

## 6.4 Package Manager

**pacman**

Modular Linux will not implement a package manager.

The installer will generate the required package set and use Arch's existing package infrastructure.

---

## 6.5 Configuration Format

**YAML**

Example:

```yaml
version: 0.1

base:
  distribution: arch

desktop:
  environment: kde
  display: wayland

hardware:
  network: true
  wifi: true
  bluetooth: true
  audio: true
  webcam: true

applications:
  - firefox
  - git
  - vscodium

filesystem:
  type: ext4

bootloader:
  type: systemd-boot
```

---

# 7. Installer Workflow

The installation workflow shall be:

```text
Boot ISO
   ↓
Initialize Live Environment
   ↓
Initialize Network
   ↓
Detect Hardware
   ↓
Welcome
   ↓
Hardware Features
   ↓
Desktop Selection
   ↓
Application Selection
   ↓
User Configuration
   ↓
Disk Configuration
   ↓
Installation Summary
   ↓
Configuration Validation
   ↓
Dependency Resolution
   ↓
Disk Partitioning
   ↓
Base Installation
   ↓
Package Installation
   ↓
System Configuration
   ↓
User Creation
   ↓
Bootloader Installation
   ↓
Configuration Export
   ↓
Installation Verification
   ↓
Reboot
```

---

# 8. Hardware Detection

The installer shall detect:

- CPU
- RAM
- GPU
- storage devices
- Ethernet
- Wi-Fi
- Bluetooth
- audio devices
- webcams
- display devices
- touchpad
- keyboard

Existing Linux utilities should be used wherever possible.

Recommended utilities:

```text
lscpu
lsblk
lspci
lsusb
ip
rfkill
udevadm
free
```

---

# 9. Hardware Feature Profiles

Hardware functionality shall be represented as modular profiles.

## 9.1 Network

```yaml
id: hardware.network
name: Networking

packages:
  - networkmanager

services:
  enable:
    - NetworkManager
```

---

## 9.2 Wi-Fi

```yaml
id: hardware.wifi
name: Wi-Fi

requires:
  - hardware.network

packages:
  - networkmanager
  - linux-firmware
```

---

## 9.3 Audio

```yaml
id: hardware.audio
name: Audio

packages:
  - pipewire
  - pipewire-audio
  - pipewire-pulse
  - wireplumber
```

---

## 9.4 Webcam

```yaml
id: hardware.webcam
name: Webcam

packages:
  - v4l-utils
```

The webcam profile should integrate with the selected audio/display stack where required.

---

## 9.5 Bluetooth

```yaml
id: hardware.bluetooth
name: Bluetooth

packages:
  - bluez
  - bluez-utils

services:
  enable:
    - bluetooth
```

---

# 10. Desktop Profiles

## 10.1 KDE Plasma

```yaml
id: desktop.kde
name: KDE Plasma

packages:
  - plasma
  - sddm

services:
  enable:
    - sddm
    - NetworkManager

display:
  protocol: wayland
```

---

## 10.2 GNOME

```yaml
id: desktop.gnome
name: GNOME

packages:
  - gnome
  - gdm

services:
  enable:
    - gdm
    - NetworkManager

display:
  protocol: wayland
```

---

## 10.3 XFCE

```yaml
id: desktop.xfce
name: XFCE

packages:
  - xfce4
  - lightdm

services:
  enable:
    - lightdm
    - NetworkManager
```

---

## 10.4 Hyprland

```yaml
id: desktop.hyprland
name: Hyprland

packages:
  - hyprland
  - waybar
  - kitty

services:
  enable:
    - NetworkManager

display:
  protocol: wayland
```

The exact package set should be validated against current Arch repositories during implementation.

---

# 11. Application Profiles

Applications shall be represented independently from desktop environments.

Example:

```yaml
id: app.firefox
name: Firefox
category: internet

packages:
  - firefox
```

V0.1 application categories:

### Internet

- Firefox
- Chromium

### Media

- VLC
- MPV
- OBS Studio

### Office

- LibreOffice

### Development

- Git
- Python
- Node.js
- VSCodium
- Neovim

### Utilities

- btop
- fastfetch
- curl
- wget
- 7zip

### Gaming

- Steam

The application catalog should remain small during v0.1.

---

# 12. Profile Directory Structure

```text
profiles/
├── base/
│   └── arch.yaml
│
├── desktop/
│   ├── kde.yaml
│   ├── gnome.yaml
│   ├── xfce.yaml
│   └── hyprland.yaml
│
├── hardware/
│   ├── network.yaml
│   ├── wifi.yaml
│   ├── bluetooth.yaml
│   ├── audio.yaml
│   ├── webcam.yaml
│   └── printing.yaml
│
└── applications/
    ├── firefox.yaml
    ├── chromium.yaml
    ├── vlc.yaml
    ├── libreoffice.yaml
    ├── git.yaml
    ├── python.yaml
    ├── vscodium.yaml
    └── steam.yaml
```

---

# 13. Dependency Resolution Engine

The dependency engine is a core v0.1 component.

Input:

```yaml
desktop: kde

hardware:
  - wifi
  - audio
  - bluetooth

applications:
  - firefox
  - vscodium
```

The resolver shall:

1. Load selected profiles.
2. Resolve profile dependencies.
3. Merge package lists.
4. Remove duplicate packages.
5. Resolve conflicts.
6. Validate required services.
7. Generate final installation plan.

Example:

```text
KDE
 ├── Plasma
 ├── SDDM
 └── Wayland

Wi-Fi
 ├── NetworkManager
 └── firmware

Audio
 ├── PipeWire
 └── WirePlumber

Bluetooth
 ├── BlueZ
 └── Bluetooth service

Firefox
 └── Firefox
```

---

# 14. Installation Plan

Before modifying the disk, the installer should generate an internal installation plan.

Example:

```yaml
base_packages:
  - base
  - linux
  - linux-firmware
  - sudo

packages:
  - plasma
  - sddm
  - networkmanager
  - pipewire
  - wireplumber
  - bluez
  - firefox
  - git
  - vscodium

services:
  - NetworkManager
  - bluetooth
  - sddm
```

The installation plan must be validated before disk modification begins.

---

# 15. Installation Summary

Before installation, the UI must show:

```text
Installation Summary

Base
Arch Linux

Desktop
KDE Plasma

Display
Wayland

Hardware
✓ Network
✓ Wi-Fi
✓ Bluetooth
✓ Audio
✓ Webcam

Applications
✓ Firefox
✓ Git
✓ VSCodium
✓ VLC

Filesystem
ext4

Bootloader
systemd-boot

Target Disk
/dev/nvme0n1

Estimated Download
2.8 GB

Estimated Installed Size
8.4 GB
```

The user must explicitly confirm before destructive disk operations.

---

# 16. Disk Management

V0.1 shall support:

### Automatic partitioning

```text
UEFI
 ├── EFI System Partition
 └── Linux filesystem
```

### Manual partitioning

Manual partitioning may be provided for advanced users.

Automatic dual-boot configuration is not required.

---

# 17. Filesystem

Primary v0.1 filesystem:

```text
ext4
```

Btrfs may be implemented experimentally but must not be a dependency for v0.1.

Future Btrfs functionality may include:

- snapshots
- rollback
- compression
- subvolumes

---

# 18. Bootloader

Primary bootloader:

```text
systemd-boot
```

Requirements:

- UEFI support
- kernel entry
- initramfs
- bootloader configuration
- boot entry creation

Legacy BIOS support is outside the primary v0.1 target.

---

# 19. User Management

The installer shall create a normal user account.

Configuration:

```text
Username
Full Name
Password
Administrator privileges
Automatic login
```

Administrative access should be provided through:

```text
sudo
```

Root login should not be enabled by default.

---

# 20. Configuration Export

After successful installation, the installer shall generate:

```text
/etc/modular/modular.yaml
```

Example:

```yaml
version: 0.1

base:
  distribution: arch

desktop:
  environment: kde
  display: wayland

hardware:
  network: true
  wifi: true
  bluetooth: true
  audio: true
  webcam: true

applications:
  - firefox
  - git
  - vscodium
  - vlc

filesystem:
  type: ext4

bootloader:
  type: systemd-boot
```

The user should also be able to save a copy externally.

---

# 21. Reproducibility

The configuration file shall become the primary representation of the installed system.

Future versions should support:

```text
modular install modular.yaml
```

This should allow another system to reproduce the selected software configuration.

For v0.1, configuration generation is required; full configuration-based reinstallation may remain experimental.

---

# 22. Project Repository Structure

```text
modular-linux/
│
├── README.md
├── LICENSE
├── VERSION
│
├── iso/
│   ├── profile/
│   ├── packages.x86_64
│   └── build.sh
│
├── installer/
│   ├── main.py
│   ├── ui/
│   ├── hardware/
│   ├── storage/
│   ├── installation/
│   └── logging/
│
├── engine/
│   ├── resolver.py
│   ├── profiles.py
│   ├── packages.py
│   ├── services.py
│   ├── validation.py
│   └── configuration.py
│
├── profiles/
│   ├── base/
│   ├── desktop/
│   ├── hardware/
│   └── applications/
│
├── schema/
│   └── modular.schema.yaml
│
├── scripts/
│   ├── build-iso.sh
│   ├── test-vm.sh
│   └── validate-profiles.py
│
├── tests/
│   ├── engine/
│   ├── hardware/
│   ├── profiles/
│   └── installation/
│
└── docs/
    ├── architecture.md
    ├── profiles.md
    └── development.md
```

---

# 23. CLI Interface

Although the primary v0.1 interface is graphical, a CLI should exist for development and testing.

Examples:

```bash
modular list desktops
```

```bash
modular list applications
```

```bash
modular hardware
```

```bash
modular resolve kde firefox audio
```

```bash
modular validate modular.yaml
```

```bash
modular generate-plan modular.yaml
```

The CLI will make automated testing significantly easier.

---

# 24. Logging

The installer shall maintain logs.

Example:

```text
/var/log/modular-installer.log
```

Logs should include:

- hardware detection
- selected profiles
- package resolution
- package installation
- partitioning
- filesystem creation
- bootloader installation
- errors

Sensitive information such as passwords must never be written to logs.

---

# 25. Error Handling

Installation failures must be explicit.

Example:

```text
Installation Failed

Component:
Package Installation

Package:
linux-firmware

Reason:
Download failed

Actions:

[ Retry ]

[ Change Mirror ]

[ Cancel Installation ]
```

The installer must not silently continue after a critical failure.

---

# 26. Security Requirements

v0.1 must:

- Use HTTPS package repositories.
- Respect Arch package signature verification.
- Avoid arbitrary remote shell execution.
- Avoid `curl | bash` installation patterns.
- Never store plaintext user passwords in configuration files.
- Never log passwords.
- Avoid unnecessary services.
- Create normal users instead of using root as the default desktop user.
- Require explicit confirmation for destructive disk operations.

---

# 27. Network Requirements

The installer may require Internet connectivity.

Expected workflow:

```text
ISO
 │
 ▼
Network
 │
 ▼
Arch Mirrors
 │
 ▼
Selected Packages
 │
 ▼
Target System
```

The ISO should not attempt to contain the entire Arch package repository.

Offline installation is outside v0.1 scope.

---

# 28. ISO Requirements

The ISO shall contain:

- Linux kernel
- initramfs
- minimal Arch live environment
- installer
- installer dependencies
- hardware detection utilities
- networking tools
- profile definitions
- configuration engine
- filesystem utilities
- boot utilities

It should not contain the complete application catalog.

---

# 29. Testing Strategy

Testing must occur at three levels.

## 29.1 Unit Testing

Test:

- YAML parsing
- profile loading
- dependency resolution
- conflict detection
- configuration validation
- package generation

---

## 29.2 Virtual Machine Testing

Use QEMU/KVM.

Minimum scenarios:

```text
Arch + KDE
Arch + GNOME
Arch + XFCE
Arch + Hyprland
Arch + no desktop
```

---

## 29.3 Physical Hardware Testing

Test on systems with:

- Intel GPU
- AMD GPU
- NVIDIA GPU
- Intel Wi-Fi
- Realtek Wi-Fi
- integrated webcam
- Bluetooth
- different audio hardware

Hardware testing should expand as the project matures.

---

# 30. v0.1 Acceptance Tests

The release is considered successful when the following scenarios work.

## Test A — Standard Desktop

```text
Base:
Arch

Desktop:
KDE

Features:
Wi-Fi
Audio
Bluetooth

Applications:
Firefox
```

Expected result:

System boots successfully into KDE and all selected functionality works.

---

## Test B — Lightweight System

```text
Base:
Arch

Desktop:
XFCE

Features:
Wi-Fi
Audio

Applications:
Firefox
```

Expected result:

System boots into XFCE with functional networking and audio.

---

## Test C — Minimal System

```text
Base:
Arch

Desktop:
None
```

Expected result:

System boots into a functional CLI environment.

---

## Test D — Developer System

```text
Base:
Arch

Desktop:
KDE

Features:
Wi-Fi
Audio
Bluetooth

Applications:
Git
Python
VSCodium
```

Expected result:

All selected applications are installed and functional.

---

## Test E — Configuration Reproduction

```text
Machine A
    ↓
Generate modular.yaml
    ↓
Machine B
    ↓
Read modular.yaml
    ↓
Resolve configuration
```

Expected result:

Machine B receives an equivalent software configuration.

---

# 31. Development Roadmap

## Milestone 0.1.1 — Profile Engine

Implement:

- YAML schema
- profile parser
- package resolver
- service resolver
- configuration validator

---

## Milestone 0.1.2 — Hardware Detection

Implement:

- CPU detection
- GPU detection
- storage detection
- network detection
- Wi-Fi detection
- Bluetooth detection
- audio detection
- webcam detection

---

## Milestone 0.1.3 — CLI

Implement:

```bash
modular hardware
modular list
modular resolve
modular validate
modular generate-plan
```

---

## Milestone 0.1.4 — Graphical Installer

Implement:

1. Welcome
2. Hardware
3. Features
4. Desktop
5. Applications
6. User
7. Disk
8. Summary
9. Installation
10. Completion

---

## Milestone 0.1.5 — Archiso

Integrate:

- installer
- engine
- profiles
- live environment
- required utilities

Build bootable ISO.

---

## Milestone 0.1.6 — VM Testing

Test complete installation using QEMU/KVM.

---

## Milestone 0.1.7 — Physical Hardware Testing

Test on multiple hardware configurations.

---

## Milestone 0.1.8 — v0.1 Release Candidate

Freeze:

- profile schema
- installer UI
- installation workflow
- configuration format

Perform full regression testing.

---

# 32. Definition of Done

Modular Linux v0.1 is complete when:

- [ ] Bootable ISO can be generated reproducibly.
- [ ] ISO boots successfully using UEFI.
- [ ] Installer launches automatically.
- [ ] Hardware is detected.
- [ ] Network can be configured.
- [ ] User can select hardware features.
- [ ] User can select a desktop environment.
- [ ] User can select applications.
- [ ] Dependency resolution works.
- [ ] Installation plan can be generated before disk modification.
- [ ] User can select installation disk.
- [ ] Automatic partitioning works.
- [ ] ext4 installation works.
- [ ] Arch base system installs correctly.
- [ ] Selected packages install correctly.
- [ ] Selected services are enabled.
- [ ] User account is created.
- [ ] sudo works.
- [ ] systemd-boot works.
- [ ] Installed system boots successfully.
- [ ] Selected desktop works.
- [ ] Selected hardware functionality works.
- [ ] Configuration is exported.
- [ ] Installer logs are generated.
- [ ] Installation errors are handled safely.
- [ ] VM installation tests pass.
- [ ] Physical hardware tests pass.

---

# 33. Future Architecture

After v0.1, the architecture can evolve into:

```text
                         MODULAR LINUX
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
           Bases           Profiles        Applications
             │                │                │
       ┌─────┼─────┐      ┌───┼────┐       ┌───┼────┐
       │     │     │      │   │    │       │   │    │
      Arch Debian Fedora Desktop Roles    Apps Repos Custom
                          │       │
                          │       ├── Developer
                          │       ├── Gaming
                          │       ├── AI
                          │       ├── Security
                          │       └── Server
                          │
                          ▼
                  Configuration Engine
                          │
                          ▼
                  Dependency Resolver
                          │
                          ▼
                     Installation
```

Future releases may therefore introduce:

- Debian base
- Fedora base
- BlackArch profile/repository
- Btrfs snapshots
- rollback
- automatic dual boot
- graphical configuration builder
- configuration sharing
- remote configuration repository
- application catalog
- custom roles
- ARM support
- offline installation
- Secure Boot
- automated hardware-specific optimization

These must remain outside the v0.1 implementation unless they become necessary to achieve the core installation workflow.

---

# 34. Core Product Philosophy

The fundamental architecture of Modular Linux should remain:

```text
                 Minimal Base
                      │
                      ▼
              Detect Hardware
                      │
                      ▼
             Select Capabilities
                      │
                      ▼
              Select Environment
                      │
                      ▼
             Select Applications
                      │
                      ▼
             Resolve Dependencies
                      │
                      ▼
              Generate System
                      │
                      ▼
             Export Configuration
```

The project should **not attempt to become another generic Linux distribution**.

The primary product is the **modular composition and installation layer**.

Arch Linux is the v0.1 foundation; it is not intended to permanently define the architecture of the project.

---

# 35. v0.1 Target Statement

> **Modular Linux v0.1 is a bootable Arch-based installation environment that allows users to construct a minimal Linux system by selecting hardware capabilities, desktop environments, and applications, while generating a reproducible configuration describing the resulting system.**

This statement defines the minimum product boundary for the first release.