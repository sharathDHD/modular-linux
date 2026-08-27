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
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86' '-b' '1M'
                             '-Xdict-size' '1M')
# NOTE: file_permissions applies *before* packages are installed, so it can
# only reference files shipped inside iso/profile/airootfs/. Package-owned
# files (/root, /etc/shadow, ...) already carry their intended modes.
file_permissions=()
