#!/usr/bin/env bash
# archiso profile definition for Modular Linux (spec §28)
set -e

iso_name="modular-linux"
iso_label="MODULAR_$(date +%Y%m)"
iso_publisher="Modular Linux <https://modular-linux.org>"
iso_application="Modular Linux Live/Installation Media"
iso_version="$(cat "$(dirname "${BASH_SOURCE[0]}")/../../VERSION" | tr -d '[:space:]')"
install_dir="modular"
workdir=${workdir:-"/tmp/modular-build"}
outdir=${outdir:-"$(dirname "$0")/../../out"}

buildmodes=('iso')
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
# zstd: ~10-20x faster compression than the old x86-filtered xz default
# (which made the squashfs step look "stuck" for 10-30+ minutes) at the
cost of a slightly larger ISO. This matches current upstream archiso releng.
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M')
# NOTE: file_permissions applies *before* packages are installed, so it can
# only reference files shipped inside iso/profile/airootfs/. Package-owned
# files (/root, /etc/shadow, ...) already carry their intended modes.
file_permissions=()
