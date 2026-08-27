"""Dependency resolution engine.

Given a user selection (desktop, hardware features, applications), the
resolver loads the required profiles, pulls in transitive dependencies,
detects conflicts and cycles, and produces a deterministic installation plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ConflictError, DependencyCycleError
from .profiles import Profile, ProfileRegistry


@dataclass
class ResolutionResult:
    selected: list[Profile] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    packages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    display_protocol: str | None = None


class Resolver:
    def __init__(self, registry: ProfileRegistry):
        self.registry = registry

    def resolve(self,
                desktop: str | None,
                hardware: list[str] | None = None,
                applications: list[str] | None = None,
                roles: list[str] | None = None) -> ResolutionResult:
        hardware = list(hardware or [])
        applications = list(applications or [])
        roles = list(roles or [])

        requested: list[str] = []
        if desktop and desktop != "none":
            requested.append(self._qualify(desktop, "desktop"))
        for role in roles:
            requested.append(self._qualify(role, "role"))
        for feature in hardware:
            # fully-qualified ids (e.g. gpu.intel, wm.sway) pass through
            requested.append(feature if "." in feature
                             else f"hardware.{feature}")
        for app in applications:
            requested.append(self._qualify(app, "app"))

        result = ResolutionResult()
        resolved: set[str] = set()
        visiting: list[str] = []

        def visit(profile_id: str) -> None:
            if profile_id in resolved:
                return
            if profile_id in visiting:
                cycle = visiting[visiting.index(profile_id):] + [profile_id]
                raise DependencyCycleError(cycle)
            profile = self.registry.get(profile_id)
            visiting.append(profile_id)
            dep_ids: list[str] = []
            for dep in profile.requires:
                visit(dep)
                dep_ids.append(dep)
            visiting.pop()
            resolved.add(profile_id)
            result.selected.append(profile)
            result.dependencies[profile_id] = dep_ids

            for pkg in profile.packages:
                if pkg not in result.packages:
                    result.packages.append(pkg)
            for svc in profile.services.enable:
                if svc not in result.services:
                    result.services.append(svc)
            if profile.display.protocol:
                result.display_protocol = profile.display.protocol

        self._check_conflicts(requested)
        for rid in requested:
            visit(rid)

        result.packages.sort()
        result.services.sort()
        return result

    @staticmethod
    def _qualify(name: str, prefix: str) -> str:
        return name if "." in name else f"{prefix}.{name}"

    def _check_conflicts(self, requested: list[str]) -> None:
        profiles = [self.registry.get(rid) for rid in requested]
        expanded = set(requested)
        for p in profiles:
            expanded.update(p.requires)
        for p in profiles:
            for c in p.conflicts:
                if c in requested or c in expanded - {p.id}:
                    raise ConflictError(p.id, c)
