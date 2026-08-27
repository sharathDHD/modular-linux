# Development Guide

## Toolchain

- Python >= 3.10 (venv at `.venv/`)
- Go >= 1.24 — CLI binary
- GCC / make — C hardware prober
- archiso + qemu (optional) — build & boot the ISO

Arch install:

```bash
sudo pacman -S --needed go rust nodejs npm cmake python-gobject gtk3 archiso
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Build Everything

```bash
make            # builds bin/modular-detect and bin/modular
```

## Run Tests

```bash
pytest                    # Python engine/installer/storage/logging tests
go test ./...             # Go resolver/config tests (in cmd/modular)
make test                 # C prober JSON smoke test
scripts/validate-profiles.py
```

## CLI Smoke Test

```bash
./bin/modular list desktops
./bin/modular resolve kde firefox audio wifi
./bin/modular validate examples/modular.yaml
./bin/modular generate-plan examples/modular.yaml
```

## Graphical Installer (dev)

```bash
source .venv/bin/activate
python installer/main.py
```

Runs on any machine with GTK3; disk operations are blocked until the
explicit confirmation dialog is accepted.

## Building the ISO

Requires Arch + archiso:

```bash
sudo pacman -S --needed archiso
scripts/build-iso.sh                 # output in out/
scripts/test-vm.sh out/*.iso        # UEFI boot in QEMU
```

## Adding a Profile

1. Create `profiles/<group>/<name>.yaml`.
2. Add id/name/category/packages/requires per docs/profiles.md.
3. `pytest tests/profiles -q` then validate with the CLI.

## Conventions

- No secrets in logs or argv (`installer/logging/setup.py` redacts).
- Destructive operations require explicit confirmation parameters.
- Both engine implementations must stay behaviorally identical; add the same
  case to `tests/engine/` and `cmd/modular/resolver_test.go`.
