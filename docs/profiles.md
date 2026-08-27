# Profiles

A profile is a small YAML file describing one selectable unit: a hardware
capability, a desktop environment, or an application (spec §9-§12).

## Layout

```text
profiles/
├── base/arch.yaml          always-installed base system
├── desktop/*.yaml          kde, gnome, xfce, hyprland
├── hardware/*.yaml         network, wifi, bluetooth, audio, webcam, printing
└── applications/*.yaml     firefox, git, python, ...
```

The **directory** determines the profile group (`desktop`, `hardware`,
`applications`); the `category:` field inside the file is free-form metadata
(e.g. `internet`, `media`).

## Fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | globally unique; `<group>.<name>` |
| `name` | yes | human-readable display name |
| `category` | yes | free-form category tag |
| `packages` | no | pacman packages to install |
| `requires` | no | profile ids pulled in transitively |
| `conflicts` | no | profile ids that cannot coexist |
| `services.enable` | no | systemd units to enable in the target |
| `display.protocol` | no | `wayland` or `x11` |

## Example

```yaml
id: desktop.kde
name: KDE Plasma
category: desktop

requires:
  - hardware.network

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

## Rules Enforced by the Resolver

1. Dependencies are resolved recursively and merged.
2. Duplicate packages/services collapse into one.
3. Cycles are rejected (`DependencyCycleError`).
4. Declared conflicts abort resolution before any change.

Validate all profiles after editing:

```bash
make test && ./bin/modular list profiles && scripts/validate-profiles.py
```
