import pytest

import engine.validation as validation
from engine.errors import ConfigurationError
from engine.configuration import ModularConfiguration
from engine.profiles import default_registry

VALID = {
    "version": 1,
    "base": {"distribution": "arch"},
    "system": {"architecture": "x86_64", "kernel": "linux", "init": "systemd"},
    "desktop": {"environment": "kde", "display": "automatic"},
    "hardware": {"network": True, "wifi": True, "bluetooth": True,
                 "audio": True, "webcam": False, "gpu": "automatic"},
    "roles": ["developer"],
    "applications": ["firefox", "git"],
    "shell": {"type": "bash"},
    "filesystem": {"type": "ext4"},
    "bootloader": {"type": "systemd-boot"},
    "sources": {"arch": True, "aur": False, "flatpak": False,
                "appimage": False},
}


@pytest.fixture(scope="module")
def registry():
    return default_registry()


def test_valid_configuration(registry):
    assert validation.validate(VALID, registry) == []


def test_unknown_desktop_rejected(registry):
    data = dict(VALID)
    data["desktop"] = {"environment": "trinity"}
    assert any("desktop" in e for e in validation.validate(data, registry))


def test_wm_selection_accepted(registry):
    data = dict(VALID)
    data["desktop"] = {"environment": "sway"}
    assert validation.validate(data, registry) == []


def test_unknown_kernel_rejected(registry):
    data = dict(VALID)
    data["system"] = {**VALID["system"], "kernel": "linux-rt"}
    errors = validation.validate(data, registry)
    assert any("kernel" in e for e in errors)


def test_aur_app_requires_explicit_source(registry):
    data = dict(VALID)
    data["applications"] = ["brave"]
    errors = validation.validate(data, registry)
    assert any("AUR" in e for e in errors)
    data["sources"] = {**VALID["sources"], "aur": True}
    assert validation.validate(data, registry) == []


def test_unsupported_distribution_rejected(registry):
    data = dict(VALID)
    data["base"] = {"distribution": "debian"}
    assert validation.validate(data, registry)


def test_grub_bootloader_now_supported(registry):
    data = dict(VALID)
    data["bootloader"] = {"type": "grub"}
    assert validation.validate(data, registry) == []


def test_shell_and_gpu_modes(registry):
    data = dict(VALID)
    data["shell"] = {"type": "fish"}
    data["hardware"] = {**VALID["hardware"], "gpu": "nvidia-proprietary"}
    assert validation.validate(data, registry) == []
    data["hardware"] = {**VALID["hardware"], "gpu": "voodoo"}
    assert any("GPU" in e for e in validation.validate(data, registry))


def test_load_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("foo: [unclosed")
    with pytest.raises(ConfigurationError):
        ModularConfiguration.load(str(bad))


def test_configuration_roundtrip_v1(tmp_path):
    cfg = ModularConfiguration.from_dict(VALID)
    path = tmp_path / "modular.yaml"
    cfg.save(str(path))
    loaded = ModularConfiguration.load(str(path))
    assert loaded.desktop_environment == "kde"
    assert loaded.kernel == "linux"
    assert loaded.roles == ["developer"]
    assert loaded.applications == ["firefox", "git"]
    assert loaded.sources["arch"] is True
    assert loaded.sources["aur"] is False


def test_export_target_matches_spec():
    assert ModularConfiguration.export_target() == "/etc/modular/modular.yaml"
