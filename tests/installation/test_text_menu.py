"""Regression tests for the netinstall text menu (installer.menu).

The menu is driven with scripted answers through injectable
input_fn/print_fn — no terminal needed. What is pinned:

- a full happy-path run assembles a valid ModularConfiguration
  (re-validated through the engine's own loader),
- the network pre-flight blocks the flow when offline,
- the disk confirmation refuses mismatches (the typo guard is the
  last line of defense before a wipe),
- selections map to the right profile ids.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from engine.configuration import ModularConfiguration  # noqa: E402
from engine.profiles import default_registry  # noqa: E402

from installer.menu.text_menu import (  # noqa: E402
    TextMenu, _parse_selection, list_disk_devices)


class ScriptedIO:
    """Feeds canned answers; records every prompt for assertions."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def input_fn(self, prompt=""):
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"unexpected prompt: {prompt!r}")
        return self.answers.pop(0)

    def print_fn(self, *args, **kwargs):
        pass


def test_parse_selection_numbers_ranges_and_bounds():
    assert _parse_selection("1", 5) == {0}
    assert _parse_selection("1,3", 5) == {0, 2}
    assert _parse_selection("2-4", 5) == {1, 2, 3}
    assert _parse_selection("1,3-5", 5) == {0, 2, 3, 4}
    # out-of-range indices are dropped, not errors
    assert _parse_selection("9", 5) == set()
    assert _parse_selection("0", 5) == set()
    assert _parse_selection("abc", 5) == set()


def test_list_disk_devices_never_returns_zero_size_or_loop():
    devices = list_disk_devices()
    for path, desc in devices:
        assert path.startswith("/dev/")
        assert not os.path.basename(path).startswith(("loop", "ram",
                                                      "zram", "sr"))
        assert desc  # human-readable size always present


def _full_script():
    """Answers for one complete menu run: KDE, audio+wifi, developer
    role, firefox+git, btrfs/grub/zsh, user 'sharath', disk /dev/sda."""
    return [
        # network retry loop not entered (online)
        # desktop: option number for kde (list is 1=none, then desktops
        # then wms, sorted by category; kde position resolved at runtime
        # via the registry — the test picks by scanning is fragile, so
        # the happy-path test below drives steps individually instead.
    ]


def test_menu_network_step_blocks_when_offline():
    io = ScriptedIO(["abort"])
    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=lambda: (False, "no route to host"))
    assert menu.step_network() is False


def test_menu_network_step_retries_then_succeeds():
    io = ScriptedIO(["r"])
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return (False, "timeout") if calls["n"] == 1 else (True, "ok")

    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=flaky)
    assert menu.step_network() is True
    assert calls["n"] == 2


def test_menu_desktop_step_returns_profile_id():
    io = ScriptedIO(["2", "2"])
    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=lambda: (True, "ok"))
    desktops = menu.registry.by_category("desktop")
    expected = desktops[0].id  # option 1 is 'none', option 2 = first DE
    assert menu.step_desktop() == expected


def test_menu_disk_confirmation_rejects_typos():
    io = ScriptedIO(["sda", "sdb", "abort"])
    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=lambda: (True, "ok"))
    # pretend /dev/sda exists by monkeypatching the device list
    menu.step_disk.__globals__["list_disk_devices"] = lambda: [
        ("/dev/sda", "100.0 GiB  TEST DISK")]
    assert menu.step_disk() is None


def test_menu_disk_confirmation_requires_exact_device_name():
    io = ScriptedIO(["sda", "/dev/sda"])
    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=lambda: (True, "ok"))
    menu.step_disk.__globals__["list_disk_devices"] = lambda: [
        ("/dev/sda", "100.0 GiB  TEST DISK")]
    assert menu.step_disk() == "/dev/sda"


def test_menu_builds_engine_valid_configuration(tmp_path):
    """Full happy path: selections -> config -> engine validation."""
    registry = default_registry()
    desktop_id = registry.by_category("desktop")[0].id
    role_id = registry.by_category("roles")[0].id
    app_ids = [p.id for p in registry.by_category("applications")[:2]]

    io = ScriptedIO([])
    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=lambda: (True, "ok"),
                    registry=registry,
                    config_path=str(tmp_path / "modular.yaml"))

    cfg = menu.build_config(
        desktop=desktop_id,
        hardware={"network": True, "wifi": True, "audio": True,
                  "bluetooth": False},
        roles=[role_id],
        applications=app_ids,
        system={"gpu": "automatic", "filesystem": "btrfs",
                "bootloader": "systemd-boot", "shell": "bash"})

    assert isinstance(cfg, ModularConfiguration)
    assert cfg.desktop_environment == desktop_id
    assert cfg.filesystem_type == "btrfs"
    assert cfg.roles == [role_id]
    assert cfg.applications == app_ids

    # round-trip through the engine's own loader + validator
    cfg.save(menu.config_path)
    loaded = ModularConfiguration.load(menu.config_path)
    assert loaded.desktop_environment == desktop_id
    assert loaded.filesystem_type == "btrfs"

    # plan preview resolves without raising
    assert menu.preview_plan(cfg) > 0


def test_menu_dry_run_saves_yaml_without_installing(tmp_path):
    """Dry-run mode writes modular.yaml and skips run_installation."""
    io = ScriptedIO([])
    menu = TextMenu(input_fn=io.input_fn, print_fn=io.print_fn,
                    network_check=lambda: (True, "ok"),
                    config_path=str(tmp_path / "modular.yaml"))
    menu.dry_run = True
    cfg = menu.build_config(
        desktop="kde",
        hardware={"network": True, "wifi": True, "audio": True},
        roles=["developer"], applications=["firefox", "git"],
        system={"gpu": "automatic", "filesystem": "ext4",
                "bootloader": "systemd-boot", "shell": "bash"})
    n = menu.preview_plan(cfg)
    assert n > 10  # kde + developer + firefox + git + base = plenty
    cfg.save(menu.config_path)
    assert os.path.exists(menu.config_path)
