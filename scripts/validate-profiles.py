#!/usr/bin/env python3
"""Validate every YAML profile in profiles/ (spec §12, §29.1).

Exits non-zero if any profile is malformed or references a dependency that
does not exist.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.profiles import default_registry
from engine.errors import ProfileError


def main() -> int:
    registry = default_registry()
    errors = []
    for profile in registry.all():
        for dep in profile.requires:
            if not registry.has(dep):
                errors.append(f"{profile.id}: missing dependency '{dep}'")
        if not profile.packages and not profile.requires:
            errors.append(f"{profile.id}: no packages and no dependencies")
    print(f"validated {len(registry)} profiles")
    for err in errors:
        print("ERROR:", err)
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProfileError as exc:
        print("FATAL:", exc)
        sys.exit(1)
