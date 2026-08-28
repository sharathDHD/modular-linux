## What does this PR do?

<!-- One or two sentences. Reference the issue number if one exists ("Closes #12"). -->

## Which layer does it touch?

- [ ] `profiles/` — declarative YAML only
- [ ] `engine/` — resolution/validation logic
- [ ] `installer/` — execution path (partitioning, pacstrap, chroot)
- [ ] `cli/` or `cmd/modular/` — command line surface
- [ ] `iso/` — live environment
- [ ] docs / CI / packaging

## Checklist

- [ ] `python -m pytest tests/` passes locally
- [ ] `python scripts/validate-profiles.py` passes (if profiles changed)
- [ ] New behavior has a regression test (execution-layer changes MUST have one — see `tests/installation/`)
- [ ] `gofmt -l .` is clean (if Go changed)
- [ ] README / docs updated if user-visible behavior changed
