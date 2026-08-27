from __future__ import annotations


class ModularError(Exception):
    """Base class for all modular-linux errors."""


class ProfileError(ModularError):
    """Raised when a profile definition is invalid or cannot be loaded."""


class ProfileNotFoundError(ModularError):
    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        super().__init__(f"unknown profile: {profile_id}")


class DependencyCycleError(ModularError):
    def __init__(self, cycle):
        self.cycle = cycle
        chain = " -> ".join(cycle)
        super().__init__(f"dependency cycle detected: {chain}")


class ConflictError(ModularError):
    def __init__(self, a: str, b: str):
        self.a = a
        self.b = b
        super().__init__(f"profile conflict: '{a}' conflicts with '{b}'")


class ConfigurationError(ModularError):
    """Raised when a modular.yaml configuration fails validation."""


class InstallationError(ModularError):
    """Raised when an installation step fails."""
