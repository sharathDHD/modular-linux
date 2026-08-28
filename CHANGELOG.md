# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.1] — 2026-08-28

### Fixed
- Install execution path could not complete a real install (found in
  code review, all pinned by new regression tests):
  - Partitioning: the sfdisk script was generated but never piped to
    sfdisk stdin — partitioning hung forever. It is now delivered via
    stdin, with `udevadm settle` between disk operations.
  - User setup: `chpasswd` never received the password stream because the
    stdin marker matched `cmd[-2:]` instead of `cmd[-1]`.
  - fstab: `genfstab` ran *inside* the chroot with a `/mnt/...` redirect
    that resolved to `/mnt/mnt/etc/fstab`. It now runs outside the chroot.
  - CLI installs: the orchestrator could not be launched (`engine` not on
    `sys.path`, missing `import os`, wrong path discovery from the Go
    wrapper). The Go CLI now invokes `python3 -m` with correct root
    detection, and the orchestrator is importable both standalone and as
    a module.
  - Bootloader: systemd-boot loader entries were missing (no
    `loader.conf`, no kernel entries, no PARTUUID, no CPU microcode), and
    `mkinitcpio -p` used a flag removed upstream (`-P` is correct now).
- GUI installer duplicated ~100 lines of the install worker; it now
    delegates to the shared `run_installation()` (one code path, as the
    README always claimed).
- Device safety check result was computed and then ignored; it is now
    enforced. Timezone/locale/keymap/hostname values are validated.

### Added
- Execution-layer regression test suite (`tests/installation/`) with a
  mocked executor pinning every command and stdin payload — the test
  count went from 80 to 102.
- dosfstools and btrfs-progs to the ISO package set (mkfs.fat / btrfs
  are needed by the partitioning step).
- grub, efibootmgr and btrfs-progs to generated plans where relevant.

### Changed
- `python -m cli resolve` treats bare hardware keywords as
  `hardware.*` (parity with the Go CLI).
- Build artifacts (5.4 MB Go binary, C binary, stale airootfs snapshot)
  removed from git history going forward and ignored via `.gitignore`.

## [0.2.0] — 2026-08-27

### Added
- v1.0 "One-Day Implementation" push: 116 profiles across hardware,
  desktop, applications, services and roles.
- Go CLI wrapper (`modular` binary) for the live ISO.
- Validation and conflict detection in the engine layer.

## [0.1] — 2026-08-27

### Added
- Initial public release: engine (resolver, profile registry, plan
  generation), GTK3 graphical installer, archiso profile, C hardware
  prober.
