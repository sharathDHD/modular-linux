# Contributing to Modular Linux

Thanks for your interest. This project is young — the fastest way to help
is profiles (pure data) and regression tests for the install path.

## Project layout (the layering rules)

```text
profiles/    declarative YAML only — no logic, no scripts
engine/      resolution + validation logic (pure Python, no side effects)
installer/   execution: partitioning, pacstrap, chroot, bootloader
cli/         Python command-line entry points
cmd/modular/ Go CLI wrapper
hardware/    C hardware prober (boot-time only)
iso/         archiso profile for the live environment
tests/       pytest suite (engine + installation layers)
```

The cardinal rule: **profiles stay declarative, the engine stays
side-effect-free, and only the installer touches the system.** If a change
makes the engine write to disk or makes a profile contain logic, it will be
rejected — see `docs/architecture.md` for the reasoning.

## Getting started

```bash
git clone https://github.com/sharathDHD/modular-linux.git
cd modular-linux
python3 -m pip install -r requirements.txt

# run the full suite (102 tests as of v0.2.1)
python3 -m pytest tests/ -v

# validate every profile against the schema
python3 scripts/validate-profiles.py

# generate a plan from an example config (no installation)
python3 -m cli generate-plan examples/<config>.yaml
```

No GTK libraries are needed for the test suite; they are only required to
launch the graphical installer on the live ISO.

## Adding or changing a profile

1. Find the right category directory under `profiles/`
   (`hardware/`, `desktop/`, `applications/`, `services/`, `roles/`).
2. Copy an existing profile in the same category as a template —
   profiles in one category share a shape.
3. Fill in the metadata (`name`, `description`, `tags`) with real
   information; descriptions are shown in the installer UI.
4. Run `python3 scripts/validate-profiles.py` — it must pass.
5. Add the profile to an appropriate example config under `examples/`
   if it demonstrates a new combination.

## Changing the engine or installer

- Engine changes need tests in `tests/engine/`.
- **Installer/execution changes need a regression test in
   `tests/installation/` that pins the exact commands run** — this suite
   exists because v0.2.0 shipped with four install-path bugs that the
   planning-only tests could not see (partitioning script never piped to
   sfdisk, passwords never reaching chpasswd, fstab written inside the
   chroot, bootloader entries missing).
- Mock the executor; never run real `pacstrap`/`sfdisk` from tests.

## Commit style

`type(scope): summary` — `fix(installer): ...`, `feat(engine): ...`,
`test(installation): ...`, `chore: ...`. Keep commits single-purpose.

## Reporting bugs

Use the bug report template and include the installer log from
`/var/log/modular/install.log` (live ISO) — "it failed" without the last
lines of output is not actionable.
