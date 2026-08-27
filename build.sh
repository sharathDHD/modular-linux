#!/usr/bin/env bash
# Modular Linux v1.0 build entry point (spec §38).
#
#   ./build.sh            build dist/modular-linux-*.iso
#   ./build.sh --clean    remove work dirs and dist/ first
#   ./build.sh --debug    verbose mkarchiso output
#   ./build.sh --test     build, then boot the ISO in QEMU/KVM
#
# Progress is reported as numbered steps with percentages; every stage
# records PASS/FAIL checkpoints and a summary is printed at the end.
# Full output: dist/build-<timestamp>.log
#
# mkarchiso requires root; this script re-executes itself with sudo
# automatically and restores user ownership of ./dist afterwards.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="$ROOT/iso/profile"

if [[ "$(id -u)" -ne 0 && "${MODULAR_NO_SUDO:-0}" != "1" ]]; then
  echo "==> mkarchiso requires root; re-running with sudo (password prompt)"
  exec sudo -E MODULAR_INVOKER="$(id -un)" \
    NO_COLOR="${NO_COLOR:-1}" bash "$ROOT/build.sh" "$@"
fi

INVOKER="${MODULAR_INVOKER:-${SUDO_USER:-}}"
WORK="${WORK:-${XDG_CACHE_HOME:-$HOME/.cache}/modular-build}"
DIST="${OUT:-$ROOT/dist}"
FLAGS=()
DO_CLEAN=0

for arg in "$@"; do
  case "$arg" in
    --clean) DO_CLEAN=1 ;;
    --debug) FLAGS+=(--debug) ;;
    --test)  FLAGS+=(--test) ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

source "$ROOT/scripts/lib/log.sh"
mkdir -p "$DIST"
ml_init "$DIST/build-$(date +%Y%m%d-%H%M%S).log"
ml_plan_total 6

restore_ownership() {
  if [[ -n "$INVOKER" && "$INVOKER" != "root" ]]; then
    chown -R "$INVOKER":"$(id -gn "$INVOKER")" "$DIST" 2>/dev/null || true
    echo "==> restored ownership of $DIST to $INVOKER"
  fi
}
trap restore_ownership EXIT

(( DO_CLEAN )) && { echo "==> cleaning workdir + dist"; rm -rf "$WORK" "$DIST"; mkdir -p "$DIST"; }

command -v ml_summary >/dev/null || source "$ROOT/scripts/lib/log.sh"

# ---- step 1: preflight -------------------------------------------------
ml_step "Preflight checks"
PREFLIGHT_OK=1
for tool in make cc go mkarchiso xorriso; do
  if command -v "$tool" >/dev/null; then
    ml_checkpoint "tool:$tool" PASS "$(command -v "$tool")"
  else
    ml_checkpoint "tool:$tool" FAIL "not found in PATH"
    PREFLIGHT_OK=0
  fi
done
free_kb=$(df -Pk "$(dirname "$WORK")" | awk 'NR==2 {print $4}')
if (( free_kb > 6 * 1024 * 1024 )); then
  ml_checkpoint "disk-space:$WORK" PASS "$((free_kb / 1024 / 1024)) GB free"
else
  ml_checkpoint "disk-space:$WORK" FAIL "$((free_kb / 1024)) MB free (need >= 6 GB)"
  PREFLIGHT_OK=0
fi
[[ -f "$PROFILE/profiledef.sh" ]] \
  && ml_checkpoint "profiledef" PASS \
  || { ml_checkpoint "profiledef" FAIL "missing"; PREFLIGHT_OK=0; }
(( PREFLIGHT_OK )) && ml_ok "environment ready" || ml_fail "preflight failed"

# ---- step 2/3: binaries --------------------------------------------------
ml_step "Build C hardware prober"
if make -C "$ROOT" c && [[ -x "$ROOT/bin/modular-detect" ]]; then
  out=$("$ROOT/bin/modular-detect" | head -c 40)
  [[ "$out" == "{"* ]] && ml_ok "JSON prober ready" || ml_warn "unexpected output: $out"
else
  ml_fail "make c failed (see log)"
fi

ml_step "Build Go CLI"
if ( cd "$ROOT/cmd/modular" && go build -o ../../bin/modular . ) \
    && [[ -x "$ROOT/bin/modular" ]] \
    && "$ROOT/bin/modular" version >/dev/null; then
  ml_ok "modular CLI $("$ROOT/bin/modular" version | awk '{print $2}')"
else
  ml_fail "go build failed (see log)"
fi

# ---- step 4: staging -----------------------------------------------------
ml_step "Stage payload into ISO profile"
STAGING="$PROFILE/airootfs/opt/modular"
rm -rf "$STAGING"; mkdir -p "$STAGING"
cp -r "$ROOT/installer" "$STAGING/installer"
cp -r "$ROOT/engine"    "$STAGING/engine"
cp -r "$ROOT/cli"       "$STAGING/cli"
cp -r "$ROOT/profiles"  "$STAGING/profiles"
cp "$ROOT/bin/modular"        "$STAGING/modular"
cp "$ROOT/bin/modular-detect" "$STAGING/modular-detect"
cp "$ROOT/examples/modular.yaml" "$STAGING/"
mkdir -p "$PROFILE/airootfs/usr/local/bin"
ln -sf /opt/modular/modular        "$PROFILE/airootfs/usr/local/bin/modular"
ln -sf /opt/modular/modular-detect "$PROFILE/airootfs/usr/local/bin/modular-detect"
n_profiles=$(find "$STAGING/profiles" -name '*.yaml' | wc -l)
[[ -x "$STAGING/modular" && "$n_profiles" -gt 50 ]] \
  && ml_ok "staged installer+engine+$n_profiles profiles" \
  || ml_fail "staging incomplete"

# ---- step 5: live environment (mkarchiso) ---------------------------------
ml_step "Build live environment + ISO (mkarchiso)"
# stale-cache fix: markers present but no artifact -> rebuild from scratch
if compgen -G "$WORK/build.*" >/dev/null && ! compgen -G "$DIST/modular*.iso" >/dev/null; then
  echo "  (stale workdir without ISO artifact -> cleaning)"
  rm -rf "$WORK"; mkdir -p "$WORK"
  ml_checkpoint "stale-workdir" WARN "cleared cached build state"
fi
MILESTONE_PCT=(15 55 70 82 88 93 99)
MILESTONE_TXT=("airootfs overlay copied" "packages installed (pacstrap)" \
  "kernel+initramfs prepared" "squashfs image created" \
  "syslinux (BIOS) configured" "systemd-boot (UEFI) configured" \
  "ISO image written (xorriso)")
MSI=0
set +e
mkarchiso -v -w "$WORK" -o "$DIST" "$PROFILE" 2>&1 | while IFS= read -r line; do
  printf '%s\n' "$line"
  case "$line" in
    *"Copying custom airootfs files..."*)      i=0 ;;
    *"Done! Packages installed successfully."*) i=1 ;;
    *"Preparing kernel and initramfs"*)         i=2 ;;
    *"Creating SquashFS image"*"Done!"*|*"SquashFS image, this may take some time"*) i=3 ;;
    *"SYSLINUX set up for BIOS booting successfully."*) i=4 ;;
    *"systemd-boot set up for UEFI booting successfully."*) i=5 ;;
    *"Creating ISO image..."*)                  i=6 ;;
    *) continue ;;
  esac
  ml_sub_inline "${MILESTONE_PCT[$i]}" "${MILESTONE_TXT[$i]}"
done
MKRC=${PIPESTATUS[0]}
set -e
printf '\n'
ISO_PATH=$(ls "$DIST"/modular*.iso 2>/dev/null | head -1 || true)
if (( MKRC == 0 )) && [[ -n "$ISO_PATH" ]]; then
  ml_ok "live ISO produced ($(du -h "$ISO_PATH" | cut -f1))"
else
  ml_fail "mkarchiso exited $MKRC — see log above"
fi

# ---- step 6: finalize ------------------------------------------------------
ml_step "Finalize artifacts"
if [[ -n "$ISO_PATH" ]]; then
  ml_checkpoint "iso-present" PASS "$(basename "$ISO_PATH")"
  sha256sum "$ISO_PATH" > "$ISO_PATH.sha256" \
    && ml_checkpoint "sha256" PASS "$(sha256sum "$ISO_PATH" | cut -c1-16)..."
  cp "$DIST"/build-*.log /dev/null 2>/dev/null || true
  ml_ok "artifacts ready in $DIST"
else
  ml_checkpoint "iso-present" FAIL "no ISO in $DIST"
  ml_fail "no artifacts to finalize"
fi

restore_ownership
if ml_summary; then
  echo "==> SUCCESS: $ISO_PATH"
else
  echo "==> BUILD FAILED — inspect the checkpoint table above."
  exit 1
fi

if [[ " ${FLAGS[*]:-} " == *" --test "* ]]; then
  echo "==> booting ISO in QEMU/KVM (UEFI headless self-test)"
  "$ROOT/scripts/test-vm.sh" --headless "$ISO_PATH"
fi
