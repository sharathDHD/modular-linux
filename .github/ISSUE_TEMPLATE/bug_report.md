---
name: Bug report
about: Something is broken or behaves incorrectly
title: "[bug] "
labels: bug
assignees: ""
---

**What happened?**
A clear description of what went wrong.

**What did you expect?**
What you expected to happen instead.

**Environment**
- Modular Linux version: `cat VERSION` from the repo / ISO boot menu
- Where it ran: [ ] live ISO boot  [ ] `modular install` CLI  [ ] GUI installer  [ ] `generate-plan` only
- Target hardware (if install-related): laptop/desktop model, CPU gen, GPU, disk type (NVMe/SATA), UEFI or BIOS
- If a config file was involved, paste the `modular.yaml`

**Log output**
```
paste relevant output here — for CLI installs, the last ~30 lines before the failure
the installer log lives at /var/log/modular/install.log on the live ISO
```

**Steps to reproduce**
1. Boot ISO / run command '...'
2. Select '...'
3. See error
