from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml

from .errors import ProfileError


@dataclass(frozen=True)
class Services:
    enable: tuple[str, ...] = ()
    disable: tuple[str, ...] = ()


@dataclass(frozen=True)
class Display:
    protocol: Optional[str] = None


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    category: str
    packages: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    services: Services = field(default_factory=Services)
    display: Display = field(default_factory=Display)
    source: Optional[str] = None
    group: Optional[str] = None
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict, source_path: Optional[str] = None,
                  group: Optional[str] = None) -> "Profile":
        if not isinstance(data, dict):
            raise ProfileError("profile must be a mapping")
        for key in ("id", "name", "category"):
            if not data.get(key):
                raise ProfileError(f"profile missing required field: {key}")
        services = data.get("services") or {}
        enable = tuple(services.get("enable") or ())
        disable = tuple(services.get("disable") or ())
        display = Display(protocol=(data.get("display") or {}).get("protocol"))
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            packages=tuple(data.get("packages") or ()),
            requires=tuple(data.get("requires") or ()),
            conflicts=tuple(data.get("conflicts") or ()),
            services=Services(enable=enable, disable=disable),
            display=display,
            source=data.get("source"),
            group=group,
            description=str(data.get("description") or ""),
        )

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
        }
        if self.packages:
            data["packages"] = list(self.packages)
        if self.requires:
            data["requires"] = list(self.requires)
        if self.conflicts:
            data["conflicts"] = list(self.conflicts)
        if self.services.enable:
            data.setdefault("services", {})["enable"] = list(self.services.enable)
        if self.services.disable:
            data.setdefault("services", {})["disable"] = list(self.services.disable)
        if self.display.protocol:
            data["display"] = {"protocol": self.display.protocol}
        return data


def _load_profile_file(path: str, group: Optional[str] = None) -> Profile:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        raise ProfileError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ProfileError(f"invalid YAML in {path}: {exc}") from exc
    try:
        return Profile.from_dict(data, source_path=path, group=group)
    except ProfileError as exc:
        raise ProfileError(f"{path}: {exc}") from exc


class ProfileRegistry:
    """Loads and indexes YAML profile definitions from a directory tree.

    Expected layout mirrors the spec:

        profiles/
        ├── base/
        ├── desktop/
        ├── hardware/
        └── applications/
    """

    CATEGORIES = ("base", "desktop", "hardware", "applications")

    def __init__(self):
        self._profiles: dict[str, Profile] = {}

    def load_directory(self, root: str) -> None:
        if not os.path.isdir(root):
            raise ProfileError(f"profile directory does not exist: {root}")
        for category in sorted(os.listdir(root)):
            category_dir = os.path.join(root, category)
            if not os.path.isdir(category_dir):
                continue
            for entry in sorted(os.listdir(category_dir)):
                if not entry.endswith((".yaml", ".yml")):
                    continue
                path = os.path.join(category_dir, entry)
                profile = _load_profile_file(path, group=category)
                if profile.id in self._profiles:
                    raise ProfileError(
                        f"duplicate profile id '{profile.id}' "
                        f"({path} vs {self._profiles[profile.id].source})"
                    )
                self._profiles[profile.id] = profile

    def get(self, profile_id: str) -> Profile:
        if profile_id not in self._profiles:
            from .errors import ProfileNotFoundError

            raise ProfileNotFoundError(profile_id)
        return self._profiles[profile_id]

    def has(self, profile_id: str) -> bool:
        return profile_id in self._profiles

    def by_category(self, category: str) -> list[Profile]:
        return [p for p in self._profiles.values()
                if p.group == category or p.category == category]

    def all(self) -> list[Profile]:
        return list(self._profiles.values())

    def __len__(self) -> int:
        return len(self._profiles)


def default_registry(profiles_dir: Optional[str] = None) -> ProfileRegistry:
    registry = ProfileRegistry()
    if profiles_dir is None:
        profiles_dir = os.environ.get(
            "MODULAR_PROFILES",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "profiles"),
        )
    registry.load_directory(profiles_dir)
    return registry
