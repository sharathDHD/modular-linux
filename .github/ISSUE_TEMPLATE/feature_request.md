---
name: Feature request
about: Suggest a new profile, target, or capability
title: "[feat] "
labels: enhancement
assignees: ""
---

**Is your request a new profile, or a change to the engine?**
- [ ] New/changed profile (a YAML under `profiles/`)
- [ ] Engine or installer change (Python under `engine/` or `installer/`)
- [ ] CLI change (Go under `cmd/modular/` or Python under `cli/`)
- [ ] Something else

**Describe the idea**
What should be possible that is not possible today?

**Which layer does it belong to?**
Profiles are declarative data and easy to accept; engine changes need a
design discussion first (see docs/architecture.md for the layering rules).

**Example**
```yaml
# If this is a profile request, sketch it:
# profiles/applications/<category>/<name>.yaml
```
