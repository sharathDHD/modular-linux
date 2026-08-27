"""Tests for the consolidated enums in engine/constants.py."""
from engine.constants import (
    ALL_SOURCES, KNOWN_HARDWARE, KNOWN_ROLES, SUPPORTED_ARCHITECTURES,
    SUPPORTED_BOOTLOADERS, SUPPORTED_DISTRIBUTIONS, SUPPORTED_ENVIRONMENTS,
    SUPPORTED_FILESYSTEMS, SUPPORTED_GPU_MODES, SUPPORTED_INIT_SYSTEMS,
    SUPPORTED_KERNELS, SUPPORTED_LOGIN_MANAGERS, SUPPORTED_SHELLS,
    SUPPORTED_WMS, SUPPORTED_DESKTOPS, THIRD_PARTY_SOURCES,
    TRUSTED_SOURCES, login_manager_for,
)
from engine.packages import (
    DESKTOP_LOGIN_MANAGER, SUPPORTED_BOOTLOADERS as PKG_BOOTLOADERS,
    SUPPORTED_FILESYSTEMS as PKG_FS, SUPPORTED_KERNELS as PKG_KERNELS,
    SUPPORTED_LOGIN_MANAGERS as PKG_LM, SUPPORTED_SHELLS as PKG_SHELLS,
    SUPPORTED_GPU_MODES as PKG_GPU,
)


def test_kernel_list_nonempty():
    assert "linux" in SUPPORTED_KERNELS
    assert len(SUPPORTED_KERNELS) >= 2


def test_supported_architectures():
    assert "x86_64" in SUPPORTED_ARCHITECTURES


def test_supported_distributions_arch_only():
    assert SUPPORTED_DISTRIBUTIONS == ("arch",)


def test_init_system_systemd_only():
    assert SUPPORTED_INIT_SYSTEMS == ("systemd",)


def test_trusted_vs_third_party():
    assert "arch" in TRUSTED_SOURCES
    assert "aur" in THIRD_PARTY_SOURCES
    assert set(ALL_SOURCES) == set(TRUSTED_SOURCES) | set(THIRD_PARTY_SOURCES)
    # Trusted and third-party must not overlap.
    assert set(TRUSTED_SOURCES).isdisjoint(set(THIRD_PARTY_SOURCES))


def test_login_manager_for_known_desktops():
    assert login_manager_for("kde") == "sddm"
    assert login_manager_for("gnome") == "gdm"
    assert login_manager_for("hyprland") == "ly"


def test_login_manager_for_unknown_returns_none():
    assert login_manager_for("unknown-de") is None


def test_constants_match_packages_module():
    """Backwards-compat: engine.packages re-exports the same values."""
    assert set(SUPPORTED_KERNELS) == set(PKG_KERNELS)
    assert set(SUPPORTED_FILESYSTEMS) == set(PKG_FS)
    assert set(SUPPORTED_BOOTLOADERS) == set(PKG_BOOTLOADERS)
    assert set(SUPPORTED_LOGIN_MANAGERS) == set(PKG_LM)
    assert set(SUPPORTED_SHELLS) == set(PKG_SHELLS)
    assert set(SUPPORTED_GPU_MODES) == set(PKG_GPU)


def test_desktop_login_manager_unchanged():
    assert DESKTOP_LOGIN_MANAGER["kde"] == "sddm"
    assert DESKTOP_LOGIN_MANAGER["sway"] == "ly"
    assert "none" not in DESKTOP_LOGIN_MANAGER  # explicit None is the value
