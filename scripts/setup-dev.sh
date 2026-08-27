#!/usr/bin/env bash
# Development environment setup for Arch/EndeavourOS (spec §39).
set -euo pipefail

sudo pacman -S --needed --noconfirm \
  base-devel git go rust nodejs npm cmake \
  python python-pip python-gobject gtk3 \
  archiso qemu-desktop edk2-ovmf \
  hwinfo inxi dosfstools e2fsprogs xorg-server-xvfb

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT"

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

make c go
pytest -q
(cd cmd/modular && go test ./...)

cat <<'EOF'

Modular Linux development environment ready:
  source .venv/bin/activate
  ./bin/modular list profiles      # CLI smoke test
  python installer/main.py         # GUI installer (needs a display or Xvfb)
  ./build.sh                       # requires network; builds dist/*.iso
EOF
