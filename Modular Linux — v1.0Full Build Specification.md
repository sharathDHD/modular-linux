# Modular Linux — Arch Edition
## v1.0 Full Build Specification — One-Day Implementation

**Project:** Modular Linux  
**Edition:** Arch Edition  
**Target Version:** v1.0  
**Implementation Target:** Functional prototype / first complete release in one development day  
**Base:** Arch Linux  
**Architecture:** x86_64 / UEFI  
**Primary Objective:** Build a bootable, configurable Arch Linux installation environment that allows users to construct their system from a minimal base using selectable hardware support, desktop environments, window managers, applications, development environments, services, and system roles.

---

# 1. Executive Summary

Modular Linux is not intended to replace Arch Linux, pacman, systemd, Linux drivers, or existing application repositories.

Instead, Modular Linux provides a **composition and installation layer on top of Arch Linux**.

The system should reuse existing technologies wherever possible.

The project must follow this rule:

> **Do not reinvent an existing Linux component when a mature, maintained implementation already exists.**

Examples:

- Use **Archiso** for ISO creation.
- Use **pacman** for package management.
- Use **systemd** for services.
- Use **NetworkManager** for networking.
- Use **PipeWire/WirePlumber** for audio.
- Use **systemd-boot** or an existing bootloader.
- Use Linux kernel drivers.
- Use existing hardware-detection tools.
- Use Arch repositories and existing package sources.
- Use existing installers/components where practical.
- Use existing libraries rather than implementing low-level functionality from scratch.

The project's unique component is the **Modular Linux composition engine and user experience**.

---

# 2. Core Concept

Traditional distribution:

```text
Distribution
     │
     ├── Desktop
     ├── Applications
     ├── Services
     ├── Drivers
     └── Configuration
```

Modular Linux:

```text
                    ARCH LINUX BASE
                          │
                          ▼
                 MODULAR COMPOSITION
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
     Hardware          Environment          Apps
        │                 │                  │
   ┌────┼────┐       ┌────┼────┐       ┌────┼────┐
   │    │    │       │    │    │       │    │    │
 WiFi Audio GPU     KDE GNOME Hypr   Browser Dev Media
   │    │    │       │    │    │       │    │    │
   └────┼────┘       └────┼────┘       └────┼────┘
        │                 │                  │
        └─────────────────┼──────────────────┘
                          ▼
                   Dependency Engine
                          │
                          ▼
                   Installation Plan
                          │
                          ▼
                    Arch System
```

---

# 3. One-Day Development Philosophy

The goal is **not** to write every component ourselves.

The goal is to integrate existing components into one coherent system.

## Priority order

```text
1. Reuse existing Arch/Linux functionality
2. Reuse existing open-source libraries
3. Reuse existing binaries
4. Reuse existing installers/tools
5. Write glue code
6. Only implement missing functionality ourselves
```

Do not spend development time creating replacements for:

- package managers
- bootloaders
- kernels
- hardware drivers
- network managers
- audio systems
- filesystems
- display servers
- desktop environments
- terminal emulators
- application repositories

---

# 4. Supported Technology Stack

There is no requirement to use one programming language.

The best language should be selected according to the task.

## Python

Primary choice for:

- installer orchestration
- profile processing
- configuration
- hardware detection integration
- dependency planning
- UI glue
- scripting
- testing

Recommended libraries:

- PyGObject / GTK
- PyYAML
- psutil
- subprocess
- pathlib
- json
- asyncio where useful

---

## Rust

Use Rust where:

- performance matters
- system-level functionality is required
- a reliable standalone binary is useful
- long-running components are needed

Potential uses:

```text
modular-core
modular-hardware
modular-resolver
```

Rust is optional for v1.0.

Python should remain the default unless Rust provides a clear advantage.

---

## Go

Use Go for:

- standalone CLI utilities
- networking utilities
- concurrent operations
- small self-contained binaries

Go can be used instead of Python where distributing a single binary is beneficial.

---

## C / C++

Use only where required for:

- low-level Linux integration
- existing libraries
- performance-critical functionality
- hardware interaction

Do not write C/C++ simply because the project is an OS project.

---

## Bash

Use Bash for:

- ISO building
- Archiso integration
- system installation commands
- bootloader commands
- filesystem operations
- packaging
- build automation

Bash should remain thin and predictable.

---

## JavaScript / TypeScript

Optional.

Use only if a web UI or desktop UI framework provides a substantial advantage.

A browser-based UI is **not required** for v1.0.

---

# 5. Existing Technologies to Reuse

## Core

```text
Arch Linux
Archiso
pacman
systemd
systemd-boot
sudo
mkinitcpio
```

---

## Hardware

```text
lscpu
lsblk
lspci
lsusb
udevadm
hwinfo
inxi
rfkill
ip
iw
free
dmidecode
```

Use whichever tools are already available and appropriate.

---

## Networking

```text
NetworkManager
nmcli
nmtui
iwd
```

NetworkManager should be the default integration.

---

## Audio

```text
PipeWire
WirePlumber
ALSA
```

---

## Bluetooth

```text
BlueZ
bluetoothctl
```

---

## Graphics

Use the existing Linux graphics stack.

Support detection for:

```text
Intel
AMD
NVIDIA
```

Do not implement GPU drivers.

Use the appropriate Arch packages and existing installation mechanisms.

---

# 6. Desktop Environment Support

The installer should expose a broad selection.

## Desktop Environments

```text
KDE Plasma
GNOME
XFCE
Cinnamon
MATE
LXQt
LXDE
Budgie
COSMIC
```

The exact package names should be resolved from the current Arch repositories instead of being hard-coded permanently.

---

# 7. Window Managers / Compositors

Support:

```text
Hyprland
Sway
i3
Openbox
awesome
bspwm
dwm
river
labwc
```

For advanced environments, provide a sensible minimal configuration.

Example:

```text
Hyprland
 ├── Hyprland
 ├── Waybar
 ├── terminal
 ├── launcher
 ├── notification daemon
 ├── wallpaper utility
 └── network/audio utilities
```

The user should be able to select:

```text
Minimal
Standard
Complete
```

for environments where appropriate.

---

# 8. Display Stack

Support:

```text
Wayland
X11
Automatic
```

Recommended default:

```text
Automatic
```

The installer should select a compatible stack based on the chosen desktop/window manager.

Do not force users to understand the distinction.

---

# 9. Hardware Feature Catalog

The installer should provide modular functionality.

## Core

```text
☑ Linux kernel
☑ Firmware
☑ Networking
☑ Time synchronization
☑ sudo
☑ User management
```

---

## Connectivity

```text
☐ Ethernet
☐ Wi-Fi
☐ Bluetooth
☐ Mobile broadband
☐ VPN
```

---

## Multimedia

```text
☐ Audio
☐ Webcam
☐ Microphone
☐ Video acceleration
☐ Bluetooth audio
```

---

## Peripherals

```text
☐ Printer
☐ Scanner
☐ USB devices
☐ Touchpad
☐ Touchscreen
☐ Game controllers
```

---

## Storage

```text
☐ NVMe
☐ SATA
☐ USB storage
☐ RAID
```

Most storage functionality should rely on the Linux kernel and existing utilities rather than separate custom modules.

---

# 10. GPU Profiles

GPU detection should automatically identify:

```text
Intel
AMD
NVIDIA
```

The installer should provide:

```text
GPU Configuration

● Automatic

○ Open-source drivers
○ NVIDIA proprietary driver
○ Advanced/manual
```

The system should select packages based on detected hardware.

Do not attempt to create or modify GPU drivers.

---

# 11. Application Catalog

The application system should be broad but repository-driven.

Applications should preferably come from:

```text
Arch repositories
Official upstream packages
Official binary releases
AppImage
Flatpak
AUR
```

However, package-source trust must be explicit.

---

# 12. Application Categories

## Browsers

```text
Firefox
Chromium
Brave
Vivaldi
```

---

## Communication

```text
Discord
Telegram
Signal
Element
```

---

## Office

```text
LibreOffice
OnlyOffice
Okular
Evince
```

---

## Media

```text
VLC
MPV
Celluloid
OBS Studio
Kdenlive
HandBrake
Audacity
```

---

## Graphics

```text
GIMP
Krita
Inkscape
Blender
ImageMagick
```

---

## Development

```text
Git
GitHub CLI
Python
Node.js
npm
pnpm
Rust
Go
GCC
Clang
CMake
Meson
Ninja
Docker
Podman
Neovim
Vim
VSCodium
```

---

## Virtualization

```text
QEMU
libvirt
virt-manager
VirtualBox
```

---

## Gaming

```text
Steam
Lutris
Heroic Games Launcher
Wine
Winetricks
Gamescope
MangoHud
```

---

## Security / Networking

```text
Wireshark
Nmap
tcpdump
OpenSSH
Ghidra
```

Security tooling should be optional and should not be installed by default.

---

## System Utilities

```text
btop
htop
fastfetch
ncdu
ripgrep
fd
fzf
jq
yq
curl
wget
rsync
tmux
zoxide
```

---

# 13. Application Source Architecture

Applications should not be hard-coded into the installer.

Use a provider architecture:

```text
providers/
├── arch/
├── aur/
├── flatpak/
├── appimage/
└── binary/
```

The installer can query the provider.

Example:

```text
Firefox
 ↓
Arch Repository
 ↓
pacman
```

For another application:

```text
Application
 ↓
Flatpak
 ↓
Flathub
```

The source should be visible to the user.

---

# 14. AUR Support

AUR support may be enabled as an advanced option.

UI:

```text
Third-party sources

☐ Enable AUR
☐ Enable Flatpak
☐ Enable AppImage
```

AUR packages must be treated differently from official Arch packages.

The installer should clearly indicate:

```text
Official Arch
Third-party AUR
Flatpak
External binary
```

Never silently install third-party software.

---

# 15. User Profiles / System Roles

Instead of requiring users to manually select hundreds of packages, provide roles.

## General Desktop

```text
Browser
Audio
Video
Office
File management
Archive tools
```

---

## Developer

```text
Git
Python
Node.js
Rust
Go
C/C++
CMake
Ninja
Docker/Podman
VSCodium
Neovim
```

---

## AI / Machine Learning

```text
Python
uv
Git
Jupyter
CUDA/ROCm where appropriate
PyTorch
ONNX
OpenCV
Docker/Podman
```

AI libraries should preferably be installed through their upstream-supported mechanisms rather than forcing enormous packages into the ISO.

---

## Gaming

```text
Steam
Wine
Proton support
Lutris
Heroic
Gamescope
MangoHud
GPU support
```

---

## Content Creator

```text
OBS
Kdenlive
GIMP
Krita
Inkscape
Blender
Audacity
```

---

## Student

```text
Firefox
LibreOffice
PDF viewer
LaTeX
Python
Git
```

---

## Server

```text
SSH
Git
Docker/Podman
system utilities
monitoring tools
```

No desktop environment required.

---

## Security Research

```text
Wireshark
Nmap
tcpdump
Ghidra
network utilities
development tools
```

BlackArch should **not** be the base in this release. A future security profile may optionally use BlackArch repositories where appropriate.

---

# 16. Installer UI

The UI should behave like a system builder rather than a traditional fixed installer.

## Screen 1 — Welcome

```text
MODULAR LINUX

Build your Arch Linux system.

[ Start ]
```

---

# 17. Screen 2 — Hardware

Display:

```text
CPU
RAM
GPU
Storage
Network
Wi-Fi
Bluetooth
Audio
Webcam
Display
```

Allow automatic detection.

---

# 18. Screen 3 — System Type

```text
What are you building?

○ Desktop
○ Developer workstation
○ Gaming system
○ AI workstation
○ Content creation
○ Server
○ Minimal system
○ Custom
```

This should populate sensible defaults.

The user can modify everything afterward.

---

# 19. Screen 4 — Desktop

```text
Choose Desktop

○ KDE Plasma
○ GNOME
○ XFCE
○ Cinnamon
○ MATE
○ LXQt
○ Budgie
○ COSMIC
○ Hyprland
○ Sway
○ i3
○ None
```

---

# 20. Screen 5 — Hardware Features

```text
Connectivity

☑ Network
☑ Wi-Fi
☑ Bluetooth

Multimedia

☑ Audio
☑ Microphone
☑ Webcam

Peripherals

☐ Printing
☐ Scanning
☐ Touchscreen

GPU

● Automatic
```

---

# 21. Screen 6 — Applications

Provide:

```text
Search applications...

Categories:

Internet
Office
Media
Graphics
Development
Gaming
System
Communication
Virtualization
Security
AI
```

Users can search rather than scroll through hundreds of entries.

---

# 22. Screen 7 — Advanced

```text
Package sources

☑ Official Arch repositories
☐ AUR
☐ Flatpak
☐ AppImage

Kernel

● linux
○ linux-lts
○ linux-zen
○ linux-hardened

Filesystem

● ext4
○ btrfs

Bootloader

● systemd-boot
○ GRUB
```

---

# 23. Kernel Selection

Support:

```text
linux
linux-lts
linux-zen
linux-hardened
```

Default:

```text
linux
```

Users should be able to select another kernel.

---

# 24. Shell Selection

Provide:

```text
bash
zsh
fish
```

Default:

```text
bash
```

Optional packages:

```text
starship
zsh-autosuggestions
zsh-syntax-highlighting
```

---

# 25. Terminal Selection

Optional:

```text
Konsole
GNOME Console
Alacritty
Kitty
Foot
WezTerm
```

The installer should avoid forcing a terminal where the desktop already provides an appropriate default unless the selected profile requires one.

---

# 26. File Manager Selection

Possible options:

```text
Dolphin
Nautilus
Thunar
Nemo
PCManFM
```

The desktop profile should normally determine the default.

---

# 27. Login / Display Manager

Support:

```text
SDDM
GDM
LightDM
Ly
None
```

Selection should normally be automatically derived from the selected desktop.

Example:

```text
KDE → SDDM
GNOME → GDM
XFCE → LightDM
No desktop → None
```

Allow advanced users to override.

---

# 28. Services

Provide an advanced service screen.

Examples:

```text
☑ NetworkManager
☑ Bluetooth
☑ PipeWire
☐ SSH
☐ Printing
☐ CUPS
☐ Docker
☐ libvirtd
☐ Avahi
```

Only enable services that are required or explicitly selected.

---

# 29. Installation Summary

The final summary should show:

```text
MODULAR LINUX

Base
Arch Linux

Role
Developer Workstation

Desktop
KDE Plasma

Kernel
linux

Display
Wayland

Hardware
✓ Wi-Fi
✓ Bluetooth
✓ Audio
✓ Webcam
✓ GPU

Applications
✓ Firefox
✓ Git
✓ Python
✓ Rust
✓ Go
✓ VSCodium
✓ Docker

Sources
✓ Arch
☐ AUR
☐ Flatpak

Filesystem
ext4

Bootloader
systemd-boot

Estimated Download
XX GB

Estimated Installed Size
XX GB
```

---

# 30. Configuration Engine

The entire installation must be representable as one configuration.

Example:

```yaml
version: 1

base:
  distribution: arch

system:
  architecture: x86_64
  kernel: linux
  init: systemd

desktop:
  environment: kde
  display: wayland
  login_manager: sddm

hardware:
  network: true
  wifi: true
  bluetooth: true
  audio: true
  webcam: true
  gpu: automatic

roles:
  - developer

applications:
  - firefox
  - vscodium
  - git
  - python
  - rust
  - go
  - docker

shell:
  type: bash

filesystem:
  type: ext4

bootloader:
  type: systemd-boot

sources:
  arch: true
  aur: false
  flatpak: false
  appimage: false
```

---

# 31. Profile Schema

Every component should have a machine-readable definition.

Example:

```yaml
id: role.developer
name: Developer Workstation
description: Development environment

packages:
  - git
  - python
  - rust
  - go
  - gcc
  - clang
  - cmake
  - ninja
  - docker
```

Applications can define:

```yaml
id: application.vscodium
name: VSCodium
source: aur

packages:
  - vscodium
```

The source should be explicitly declared.

---

# 32. Dependency Resolution

The resolver must produce:

```text
Selected Profiles
       ↓
Dependencies
       ↓
Package Graph
       ↓
Conflict Detection
       ↓
Package Deduplication
       ↓
Service Resolution
       ↓
Installation Plan
```

Example conflict:

```text
GNOME
    ↓
GDM

KDE
    ↓
SDDM
```

If the user selects both desktop environments, the installer should either:

1. Support both cleanly, or
2. Ask which login manager should be default.

It must not silently overwrite one with another.

---

# 33. Hardware-Aware Package Selection

Example:

```text
Detected:

GPU = NVIDIA
```

Resolver:

```text
GPU Profile
     ↓
NVIDIA packages
     ↓
Required firmware
     ↓
Display integration
```

AMD:

```text
GPU Profile
     ↓
Mesa
Vulkan
Firmware
```

Intel:

```text
GPU Profile
     ↓
Mesa
Intel media support
Firmware
```

Exact package selection must be validated against the currently available Arch repositories.

---

# 34. Installation Engine

The installer should use a clear separation:

```text
UI
 ↓
Configuration
 ↓
Resolver
 ↓
Installation Plan
 ↓
Executor
```

The UI must not directly perform package installation.

This makes testing easier.

---

# 35. Installation Executor

Responsibilities:

```text
Partition disk
Format filesystem
Mount filesystem
Install Arch base
Install packages
Generate fstab
Configure locale
Configure timezone
Configure hostname
Create users
Configure sudo
Configure networking
Configure services
Install bootloader
Generate initramfs
Write configuration
```

Where possible, use existing Arch tooling.

---

# 36. Arch Installation

The base system should be installed using established Arch mechanisms rather than implementing a custom package installation system.

Conceptually:

```text
pacstrap
   ↓
/mnt
   ↓
arch-chroot
   ↓
system configuration
   ↓
bootloader
```

The exact implementation should follow current Arch documentation and package conventions.

---

# 37. Hardware Detection Architecture

Use a hardware abstraction layer:

```text
hardware/
├── cpu
├── gpu
├── network
├── wifi
├── bluetooth
├── audio
├── webcam
├── storage
└── display
```

Each detector returns structured information.

Example:

```json
{
  "type": "gpu",
  "vendor": "AMD",
  "model": "Radeon",
  "pci_id": "...."
}
```

The resolver consumes this information.

---

# 38. Build System

The ISO build should be automated.

Primary command:

```bash
./build.sh
```

Expected result:

```text
dist/
└── modular-linux-arch-x86_64.iso
```

Optional:

```bash
./build.sh --clean
./build.sh --debug
./build.sh --test
```

---

# 39. Development Environment

Recommended development machine:

```text
Arch Linux / EndeavourOS
```

Install development dependencies using the native package manager.

The project should provide:

```text
scripts/setup-dev.sh
```

This script prepares:

- Python environment
- required libraries
- Rust toolchain if used
- Go toolchain if used
- ISO build dependencies
- testing tools

---

# 40. Automated Testing

Before generating a release ISO:

```text
Profile validation
       ↓
Unit tests
       ↓
Resolver tests
       ↓
Configuration tests
       ↓
ISO build
       ↓
VM boot test
       ↓
Installation test
```

---

# 41. VM Testing

Use:

```text
QEMU/KVM
```

Automated test scenario:

```text
Build ISO
 ↓
Start VM
 ↓
Boot ISO
 ↓
Run installer
 ↓
Install predefined configuration
 ↓
Reboot
 ↓
Verify boot
 ↓
Verify desktop
 ↓
Verify networking
 ↓
Verify installed packages
```

---

# 42. One-Day Build Priority

The project should be implemented in this order.

## Phase 1 — Project skeleton

```text
Repository
Profiles
Configuration schema
Build scripts
```

---

## Phase 2 — Profile engine

Implement:

```text
YAML loader
Package resolver
Service resolver
Configuration validator
```

---

## Phase 3 — CLI

Implement:

```bash
modular hardware
modular list
modular resolve
modular validate
modular plan
```

---

## Phase 4 — Installer UI

Implement:

```text
Welcome
Hardware
Role
Desktop
Features
Applications
Advanced
User
Disk
Summary
Install
Complete
```

---

## Phase 5 — Arch installation engine

Integrate:

```text
pacstrap
arch-chroot
genfstab
systemd
systemd-boot
```

and existing Arch utilities.

---

## Phase 6 — Archiso

Create:

```text
modular-linux-arch-x86_64.iso
```

---

## Phase 7 — Automated VM Test

Test:

```text
KDE
GNOME
XFCE
Hyprland
No desktop
Developer
Gaming
Minimal
```

---

# 43. One-Day Definition of Done

The project should be considered successfully implemented when a developer can run:

```bash
./build.sh
```

and receive:

```text
dist/modular-linux-arch-x86_64.iso
```

The ISO must boot in QEMU/KVM.

The installer must allow a user to select:

```text
Base
Hardware
Desktop
Window manager
Kernel
Services
Applications
Shell
Filesystem
Bootloader
```

The installer must then:

```text
Detect hardware
       ↓
Resolve configuration
       ↓
Generate installation plan
       ↓
Install Arch
       ↓
Install selected software
       ↓
Configure system
       ↓
Create user
       ↓
Install bootloader
       ↓
Generate modular.yaml
       ↓
Boot installed system
```

---

# 44. Performance Requirements

The installer itself should remain lightweight.

Avoid:

- unnecessary daemons
- unnecessary background processes
- bundled application databases
- huge ISO contents
- duplicated package repositories
- custom package compilation

The ISO should primarily contain:

```text
Installer
System tools
Profile definitions
Required dependencies
```

Applications should be downloaded during installation.

---

# 45. Repository Strategy

The project should not mirror Arch repositories.

Use:

```text
Official Arch mirrors
```

For third-party sources:

```text
AUR
Flatpak
Official upstream binaries
AppImage
```

The source should be recorded in the generated configuration.

---

# 46. Binary Reuse Policy

If an existing project provides a suitable binary:

> Use it.

Examples:

```text
Existing binary
       ↓
Validate source
       ↓
Install
       ↓
Configure
```

Do not rewrite it in C, C++, Rust, Go, or Python merely for the sake of owning the implementation.

The project's code should focus on orchestration.

---

# 47. Language Selection Policy

Use the simplest suitable technology.

| Task | Preferred |
|---|---|
| ISO build | Bash |
| Installer logic | Python |
| YAML/configuration | Python |
| GUI | Python + GTK |
| Hardware integration | Python + Linux tools |
| System daemon | Rust/Go if needed |
| CLI binary | Go/Rust/Python |
| Low-level functionality | C/Rust |
| Package management | pacman |
| Bootloader | systemd-boot |
| Services | systemd |
| Networking | NetworkManager |
| Audio | PipeWire |
| ISO generation | Archiso |

There is no requirement that the project use all listed languages.

---

# 48. Security Model

The project must distinguish between:

```text
Trusted
├── Arch official repositories
└── Official Arch packages

Third-party
├── AUR
├── Flatpak
├── AppImage
└── External binaries
```

Third-party sources must never be enabled invisibly.

The installer should clearly display:

```text
⚠ Third-party package source
```

before installation.

---

# 49. Recovery

The installer should provide basic failure recovery.

If package installation fails:

```text
Retry
Change mirror
Open terminal
Cancel
```

If installation fails after disk modification:

```text
View log
Open shell
Restart installer
```

All important operations should be logged.

---

# 50. Installer Logs

Recommended:

```text
/var/log/modular/installer.log
```

Include:

```text
hardware detection
selected configuration
resolved packages
disk operations
package installation
service configuration
bootloader configuration
errors
```

Never log:

```text
passwords
private keys
tokens
```

---

# 51. Configuration Validation

Before installation:

```text
Configuration
      ↓
Schema validation
      ↓
Dependency validation
      ↓
Hardware compatibility
      ↓
Package availability
      ↓
Conflict detection
      ↓
Installation plan
```

The installer should refuse to begin destructive operations if critical validation fails.

---

# 52. Future-Proof Architecture

Although v1.0 is Arch-only, avoid hard-coding Arch assumptions into the entire codebase.

Use:

```text
backend/
├── arch/
└── future/
```

The future architecture may become:

```text
Modular Core
      │
      ├── Arch Backend
      ├── Debian Backend
      ├── Fedora Backend
      └── Other Backends
```

However, **no non-Arch backend is required for this release**.

---

# 53. Future Modular Repository Architecture

Later, the project can maintain its own profile repository:

```text
profiles.modular-linux.org
```

Conceptually:

```text
Installer
    ↓
Profile Repository
    ↓
Profile definitions
    ↓
Arch repositories
    ↓
Installation
```

The profile repository should contain metadata, not copies of large packages.

---

# 54. Future Configuration Sharing

A user could eventually share:

```text
developer-workstation.yaml
gaming-pc.yaml
ai-workstation.yaml
minimal-laptop.yaml
```

Another user could import it:

```bash
modular install developer-workstation.yaml
```

This turns configurations into portable system definitions.

---

# 55. Future GUI Builder

A future web interface could generate:

```yaml
version: 1

base:
  distribution: arch

role:
  - developer

desktop:
  environment: kde

applications:
  - firefox
  - vscodium
  - git
```

The ISO could then import that configuration.

This is intentionally not required for the first build.

---

# 56. Important Architectural Rule

The installer should **never become a giant collection of special cases**.

Avoid:

```python
if kde:
    ...
elif gnome:
    ...
elif xfce:
    ...
elif hyprland:
    ...
```

throughout the project.

Instead:

```text
Profile
 ↓
Metadata
 ↓
Resolver
 ↓
Installation plan
```

This allows new desktops, applications, and features to be added by adding profiles rather than rewriting the installer.

---

# 57. Final v1.0 Architecture

```text
                         ┌──────────────────────┐
                         │   Modular Linux ISO  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Live Arch System   │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       Modular Installer       │
                    └───────────────┬───────────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
        Hardware                 Profiles             Applications
        Detection               / Roles               / Sources
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    │
                                    ▼
                           Configuration Engine
                                    │
                                    ▼
                           Dependency Resolver
                                    │
                                    ▼
                           Installation Plan
                                    │
                                    ▼
                         Arch Installation Layer
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
           pacman                systemd             bootloader
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                                    ▼
                           Installed Arch System
                                    │
                                    ▼
                              modular.yaml
```

---

# 58. Final Product Definition

Modular Linux v1.0 is an **Arch-based modular Linux system builder**, not a replacement Linux distribution.

Its unique value is:

```text
Minimal ISO
     +
Hardware Detection
     +
Profile System
     +
Dependency Resolution
     +
Application Selection
     +
Automated Arch Installation
     +
Reproducible Configuration
```

The project should rely heavily on the existing Arch/Linux ecosystem.

The guiding engineering principle is:

> **Integrate first. Implement second.**

If Linux already has a mature component for a task, Modular Linux should configure and orchestrate it rather than replace it.

The first complete release should therefore focus the majority of custom development on:

```text
1. Profile schema
2. Configuration engine
3. Dependency resolution
4. Hardware-to-profile mapping
5. Installer UI
6. Installation orchestration
7. Configuration export
8. ISO integration
```

Everything else should be provided by existing Arch/Linux components wherever possible.

---

# 59. v1.0 Success Criteria

The project succeeds when a user can:

```text
Download ISO
     ↓
Boot USB
     ↓
Detect hardware
     ↓
Choose "Developer Workstation"
     ↓
Choose KDE
     ↓
Enable Wi-Fi + Audio + Bluetooth
     ↓
Select Firefox + VSCodium + Git + Python + Rust + Go
     ↓
Select ext4
     ↓
Select systemd-boot
     ↓
Create user
     ↓
Review installation
     ↓
Install
     ↓
Reboot
     ↓
Receive a clean Arch system
     ↓
Get modular.yaml
```

The same architecture must also support:

```text
Minimal system
Desktop workstation
Developer workstation
Gaming workstation
AI workstation
Content-creation workstation
Server
Security workstation
Custom system
```

without requiring separate operating-system images for each configuration.

---

# 60. Project Mission

> **Build the Linux system the user actually wants instead of installing a generic system and removing everything they do not want.**

Modular Linux should make the Arch philosophy accessible through a modern, hardware-aware, graphical system builder while retaining the power, flexibility, and package ecosystem of Arch Linux.