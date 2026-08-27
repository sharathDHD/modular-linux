import pytest

from engine.packages import (
    InstallationPlan, base_packages, build_plan, derive_login_manager,
)
from engine.profiles import default_registry
from engine.resolver import Resolver


@pytest.fixture(scope="module")
def registry():
    return default_registry()


def test_base_packages_kernel_swap():
    assert base_packages("linux")[1] == "linux"
    assert base_packages("linux-lts")[1] == "linux-lts"
    assert base_packages("linux-zen")[:1] == ["base"]
    with pytest.raises(ValueError):
        base_packages("linux-rt")


def test_plan_contains_base_packages(registry):
    resolution = Resolver(registry).resolve(None, [], [])
    plan = build_plan(resolution)
    for pkg in ("base", "linux", "linux-firmware", "sudo"):
        assert pkg in plan.base_packages
    assert plan.all_packages()


def test_full_developer_plan(registry):
    resolution = Resolver(registry).resolve(
        "kde", ["wifi", "audio", "bluetooth", "gpu.intel"],
        ["firefox"], roles=["developer"])
    plan = build_plan(resolution, desktop_id="kde",
                      hardware=["wifi", "audio", "bluetooth"],
                      roles=["developer"])
    pkgs = set(plan.all_packages())
    for pkg in ("plasma", "sddm", "git", "rustup", "mesa", "vulkan-intel",
                "pipewire"):
        assert pkg in pkgs
    services = set(plan.services)
    assert {"NetworkManager", "sddm"} <= services
    assert plan.login_manager == "sddm"
    assert plan.roles == ["developer"]


def test_login_manager_derivation_and_override(registry):
    assert derive_login_manager("desktop.gnome") == "gdm"
    assert derive_login_manager("wm.sway") == "ly"
    assert derive_login_manager("desktop.kde", override="lightdm") == "lightdm"


def test_services_normalized():
    from engine.services import normalize_services, systemd_enable_commands

    assert normalize_services(["sddm", "sddm", "", " NetworkManager "]) == \
        ["NetworkManager", "sddm"]
    cmds = systemd_enable_commands(["bluetooth"])
    assert cmds == [["systemctl", "--root", "/mnt", "enable", "bluetooth.service"]]


def test_aur_packages_routed_separately(registry):
    """AUR-flagged applications land in aur_packages, not packages."""
    resolution = Resolver(registry).resolve(
        None, ["network"], ["app.brave"], roles=[])
    plan = build_plan(resolution, kernel="linux",
                      filesystem="ext4", bootloader="systemd-boot",
                      shell="bash", desktop_id="none",
                      sources={"arch": True, "aur": True, "flatpak": False,
                               "appimage": False})
    assert "brave-bin" in plan.aur_packages
    assert "brave-bin" not in plan.packages


def test_official_packages_not_in_aur(registry):
    """Official-repo packages stay in packages, not aur_packages."""
    resolution = Resolver(registry).resolve(
        "kde", ["network"], ["firefox"], roles=[])
    plan = build_plan(resolution, kernel="linux",
                      filesystem="ext4", bootloader="systemd-boot",
                      shell="bash", desktop_id="kde",
                      sources={"arch": True, "aur": False, "flatpak": False,
                               "appimage": False})
    assert "firefox" in plan.packages
    assert "firefox" not in plan.aur_packages
    # KDE itself is official.
    assert "plasma" in plan.packages or any("plasma" in p for p in plan.packages)
