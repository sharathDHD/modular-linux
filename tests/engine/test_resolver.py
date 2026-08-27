import pytest

from engine.errors import ConflictError, DependencyCycleError, ProfileNotFoundError
from engine.profiles import ProfileRegistry, default_registry
from engine.resolver import Resolver


@pytest.fixture()
def registry():
    return default_registry()


def test_registry_loads_all_categories(registry):
    assert registry.has("base.arch")
    for cat in ("desktop", "hardware", "applications"):
        assert len(registry.by_category(cat)) > 0


def test_resolve_kde_with_wifi_audio(registry):
    result = Resolver(registry).resolve("kde", ["wifi", "audio"], ["firefox"])
    pkgs = set(result.packages)
    assert "plasma" in pkgs
    assert "firefox" in pkgs
    assert "networkmanager" in pkgs  # wifi -> network (transitive)
    assert "NetworkManager" in result.services
    assert "sddm" in result.services
    assert result.display_protocol == "wayland"


def test_resolver_deduplicates_packages(registry):
    result = Resolver(registry).resolve("kde", ["wifi"], [])
    assert len(result.packages) == len(set(result.packages))


def test_unknown_profile_raises(registry):
    with pytest.raises(ProfileNotFoundError):
        Resolver(registry).resolve("doesnotexist")


def test_cycle_detection():
    from engine.profiles import Profile

    reg = ProfileRegistry()
    reg._profiles["a.x"] = Profile(id="a.x", name="X", category="base",
                                   requires=("a.y",))
    reg._profiles["a.y"] = Profile(id="a.y", name="Y", category="base",
                                   requires=("a.x",))
    with pytest.raises(DependencyCycleError):
        Resolver(reg).resolve("a.x")


def test_conflict_detection():
    from engine.profiles import Profile

    reg = ProfileRegistry()
    reg._profiles["desktop.one"] = Profile(id="desktop.one", name="One",
                                           category="desktop",
                                           conflicts=("desktop.two",))
    reg._profiles["desktop.two"] = Profile(id="desktop.two", name="Two",
                                           category="desktop")
    with pytest.raises(ConflictError):
        Resolver(reg).resolve("desktop.one", applications=["desktop.two"])
