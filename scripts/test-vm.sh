#!/usr/bin/env bash
# Boot a built Modular Linux ISO in QEMU/KVM (spec §41).
#
#   scripts/test-vm.sh <iso>              interactive UEFI window
#   scripts/test-vm.sh --headless <iso>   serial-console self-test, no window
#
# Headless mode waits for the in-ISO smoke service markers
# (MODULAR-SMOKE-BEGIN/END) on the serial console and reports checkpoints.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/log.sh"

MODE="interactive"
ISO=""
for arg in "$@"; do
  case "$arg" in
    --headless) MODE="headless" ;;
    *) ISO="$arg" ;;
  esac
done
[[ -n "$ISO" && -f "$ISO" ]] || { echo "usage: test-vm.sh [--headless] <iso>" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || {
  echo "error: qemu-system-x86_64 not found (pacman -S qemu-desktop)" >&2; exit 1; }

OVMF_CODE="" OVMF_VARS=""
for c in /usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/ovmf/x64/OVMF_CODE.fd; do
  [[ -f "$c" ]] && { OVMF_CODE="$c"; break; }
done
[[ -n "$OVMF_CODE" ]] || { echo "error: OVMF firmware not found" >&2; exit 1; }
V="${OVMF_CODE%_CODE*}_VARS${OVMF_CODE##*_CODE}"
[[ -f "$V" ]] || V="$(dirname "$OVMF_CODE")/OVMF_VARS.fd"
WORKDIR="$(mktemp -d /tmp/opencode/modular-vm.XXXX)"
cp "$V" "$WORKDIR/VARS.fd"
chmod +w "$WORKDIR/VARS.fd"

KVM_ARGS=()
if [[ -w /dev/kvm ]]; then KVM_ARGS=(-enable-kvm); else
  echo "(no /dev/kvm access -> using TCG emulation, slower boot)"; fi

QEMU=(qemu-system-x86_64 "${KVM_ARGS[@]}" -m 2048 -smp 4
      -device qemu-xhci -device usb-kbd -device usb-tablet
      -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE"
      -drive if=pflash,format=raw,file="$WORKDIR/VARS.fd"
      -cdrom "$ISO" -boot d -no-reboot)

if [[ "$MODE" == "interactive" ]]; then
  exec "${QEMU[@]}"
fi

# ---- headless self-test ----------------------------------------------------
ml_plan_total 3
SERIAL_LOG="$WORKDIR/serial.log"
TIMEOUT="${VM_TIMEOUT:-420}"

ml_step "Boot ISO (UEFI, serial console)"
"${QEMU[@]}" -display none -serial file:"$SERIAL_LOG" &
QPID=$!
trap 'kill $QPID 2>/dev/null; wait $QPID 2>/dev/null' EXIT

found_begin=0; found_end=0; waited=0
while (( waited < TIMEOUT )); do
  if (( ! found_begin )) && grep -q "MODULAR-SMOKE-BEGIN" "$SERIAL_LOG" 2>/dev/null; then
    found_begin=1; ml_ok "live system booted (smoke service started)"
  fi
  if (( found_begin )) && grep -q "MODULAR-SMOKE-END" "$SERIAL_LOG" 2>/dev/null; then
    found_end=1; ml_ok "smoke service finished"; break
  fi
  sleep 5; waited=$((waited + 5))
  (( waited % 60 == 0 )) && echo "  ...waiting (${waited}s/${TIMEOUT}s)"
done
(( found_end )) || ml_fail "timed out after ${TIMEOUT}s — see $SERIAL_LOG"

ml_step "Verify in-ISO tooling output"
grep -E "modular 1\.[0-9.]+" "$SERIAL_LOG" \
  && ml_checkpoint "cli-version" PASS "$(grep -o 'modular [0-9.]*' "$SERIAL_LOG" | head -1)" \
  || ml_checkpoint "cli-version" FAIL "version line missing"
grep -q "role.developer\|role.general" "$SERIAL_LOG" \
  && ml_checkpoint "profile-engine" PASS "roles listed inside live env" \
  || ml_checkpoint "profile-engine" FAIL "role listing missing"
grep -q "SMOKE-VALIDATE-OK" "$SERIAL_LOG" \
  && ml_checkpoint "config-validation" PASS "examples/modular.yaml valid in live env" \
  || ml_checkpoint "config-validation" FAIL "validation marker missing"
detect_line=$(grep -m1 '"cores"' "$SERIAL_LOG" | tr -d ' ')
[[ -n "$detect_line" ]] \
  && ml_checkpoint "hardware-detect" PASS "$detect_line" \
  || ml_checkpoint "hardware-detect" FAIL "modular-detect produced no JSON"

ml_step "Summary"
kill "$QPID" 2>/dev/null || true
cp "$SERIAL_LOG" "$(dirname "$ISO")/vm-serial.log" 2>/dev/null || true
echo "  full serial log: $(dirname "$ISO")/vm-serial.log"
if ml_summary; then
  echo "==> VM SELF-TEST PASSED"
  exit 0
fi
echo "==> VM SELF-TEST FAILED"
exit 1
