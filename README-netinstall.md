# Netinstall Edition

The `netinstaller` branch builds a **minimal online installer ISO**. The
main branch ISO and this one both install *online* — packages are
downloaded from the Arch mirrors by pacstrap at install time, never
copied from the ISO. The difference is what the **live environment**
carries:

| | main | netinstaller |
|---|---|---|
| Live session | GTK3 graphical builder | console + text menu |
| Packages in live env | 27 (incl. gtk3, git, vim, ssh, tmux) | 19 (boot, network drivers, python) |
| Wi-Fi / ethernet drivers | yes | yes — **required to install** |
| Installer UI | GTK GUI, CLI | text menu (tty1), CLI |
| Typical ISO size | larger | ~25-30% smaller (no GTK/toolchain) |

The philosophy: the ISO contains *only* what is needed to boot, get on
the network, and run the menu. Every package you select — desktop,
applications, everything — is downloaded when the install runs.

## Boot flow

1. Boot the ISO (BIOS or UEFI). Root autologins on tty1.
2. `~root/.bash_profile` launches `modular-menu` (the text menu).
3. The menu checks the network first. Ethernet is plug-and-play via
   NetworkManager. For Wi-Fi, press Alt+F2, run `nmtui`, connect, and
   return (the menu offers to re-check).
4. Walk the eight steps: desktop/WM, hardware, roles, applications,
   system choices (GPU/filesystem/bootloader/shell), user identity,
   target disk.
5. The menu resolves the plan and shows the package count that *will be
   downloaded*, saves `/root/modular.yaml`, and asks to proceed.
6. `run_installation()` downloads and installs the system — the same
   orchestrator the GTK GUI and `modular install` CLI use.

## Running it manually

```bash
# the menu (what tty1 runs automatically)
python3 -m installer.menu

# stop after writing modular.yaml + plan preview
python3 -m installer.menu --dry-run

# headless, no menu at all
MODULAR_INSTALL_DEVICE=/dev/sda \
MODULAR_INSTALL_PASSWORD=secret \
python3 -m cli install /root/modular.yaml
```

The graphical installer code is still present in the repo on this
branch — it just is not shipped in the netinstall live environment
(no GTK in the package list). Nothing else is forked: engine,
orchestrator, profiles and tests are shared 1:1 with `main`.

## Building

```bash
./build.sh              # dist/modular-linux-*.iso (netinstall edition)
./build.sh --test       # boot it in QEMU/UEFI for a self-test
```

`scripts/test-vm.sh --headless` boots the ISO and watches for the
smoke-service markers (`MODULAR-SMOKE-BEGIN/END`) on the console.

## Keeping this branch healthy

- Rebase onto `main` regularly — this branch must never fork installer
  logic; it only differs in *packaging* (live-env package list, tty
  launcher, docs).
- Long term, consider replacing the branch with a build-time switch
  (`./build.sh --edition=netinstall` selecting a different package
  list) so one branch ships two editions.
