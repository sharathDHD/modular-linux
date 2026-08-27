#!/usr/bin/env bash
# Build the Modular Linux live ISO with archiso (spec §28, Milestone 0.1.5).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/iso/profile"
WORK="${WORK:-/tmp/modular-build}"
OUT="${OUT:-$ROOT/out}"

command -v mkarchiso >/dev/null || {
  echo "error: mkarchiso not found (pacman -S archiso)" >&2
  exit 1
}

echo "==> building host binaries (C prober + Go CLI)"
make -C "$ROOT" c go

STAGING="$PROFILE/airootfs/opt/modular"
rm -rf "$STAGING"
mkdir -p "$STAGING"

echo "==> staging installer + engine + profiles"
cp -r "$ROOT/installer" "$STAGING/installer"
cp -r "$ROOT/engine"    "$STAGING/engine"
cp -r "$ROOT/cli"       "$STAGING/cli"
cp -r "$ROOT/profiles"  "$STAGING/profiles"
cp "$ROOT/bin/modular"         "$STAGING/modular"
cp "$ROOT/bin/modular-detect"  "$STAGING/modular-detect"
cp "$ROOT/examples/modular.yaml" "$STAGING/"

mkdir -p "$PROFILE/airootfs/usr/local/bin"
ln -sf /opt/modular/modular        "$PROFILE/airootfs/usr/local/bin/modular"
ln -sf /opt/modular/modular-detect "$PROFILE/airootfs/usr/local/bin/modular-detect"

echo "==> running mkarchiso"
mkdir -p "$OUT"
mkarchiso -v -w "$WORK" -o "$OUT" "$PROFILE"

echo "==> done: $(ls "$OUT"/modular-linux-*.iso 2>/dev/null || echo '(no iso produced)')"
