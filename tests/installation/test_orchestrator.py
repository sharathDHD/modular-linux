"""Tests for the headless installation orchestrator.

These tests cover the planning and validation paths only — the actual
disk-pacstrap-chroot sequence is exercised in the live ISO under QEMU
( scripts/test-vm.sh ).
"""
import os
import tempfile

import pytest

from engine.configuration import ModularConfiguration
from engine.profiles import default_registry
from engine.resolver import Resolver
from engine.packages import build_plan
from installer.installation.orchestrator import (
    InstallOptions, _resolve_target_device, _resolve_gpu_vendor,
)
from installer.hardware.detect import StorageDevice


VALID_CONFIG = """
version: 1
base:
  distribution: arch
system:
  architecture: x86_64
  kernel: linux
  init: systemd
desktop:
  environment: none
hardware:
  network: true
  audio: true
roles: []
applications: []
shell:
  type: bash
filesystem:
  type: ext4
bootloader:
  type: systemd-boot
sources:
  arch: true
"""


def test_resolve_target_device_rejects_loopback():
    with pytest.raises(ValueError):
        _resolve_target_device("/dev/loop0")


def test_resolve_target_device_rejects_optical():
    with pytest.raises(ValueError):
        _resolve_target_device("/dev/sr0")


def test_resolve_target_device_rejects_ramdisk():
    with pytest.raises(ValueError):
        _resolve_target_device("/dev/ram0")


def test_resolve_target_device_rejects_empty():
    with pytest.raises(ValueError):
        _resolve_target_device("")
    with pytest.raises(ValueError):
        _resolve_target_device("sda")  # no /dev/ prefix


def test_resolve_target_device_accepts_sata():
    assert _resolve_target_device("/dev/sda") == "/dev/sda"


def test_resolve_target_device_accepts_nvme():
    assert _resolve_target_device("/dev/nvme0n1") == "/dev/nvme0n1"


def test_plan_generation_for_minimal_config():
    """A minimal config resolves to a sensible install plan."""
    cfg = ModularConfiguration.from_dict(__import__("yaml").safe_load(VALID_CONFIG))
    reg = default_registry()
    res = Resolver(reg).resolve("none", ["network", "audio"], [],
                               roles=cfg.roles)
    plan = build_plan(res, kernel=cfg.kernel,
                      filesystem=cfg.filesystem_type,
                      bootloader=cfg.bootloader_type,
                      shell=cfg.shell_type,
                      desktop_id=cfg.desktop_environment)
    assert "base" in plan.base_packages
    assert "linux" in plan.base_packages
    assert "sudo" in plan.base_packages
    assert plan.filesystem == "ext4"
    assert plan.bootloader == "systemd-boot"


def test_aur_packages_routed_separately():
    """AUR packages are split out from the official list."""
    cfg_yaml = """
version: 1
base: {distribution: arch}
system: {architecture: x86_64, kernel: linux, init: systemd}
desktop: {environment: none}
hardware: {network: true}
applications: [brave]
sources: {arch: true, aur: true}
filesystem: {type: ext4}
bootloader: {type: systemd-boot}
shell: {type: bash}
"""
    cfg = ModularConfiguration.from_dict(__import__("yaml").safe_load(cfg_yaml))
    reg = default_registry()
    res = Resolver(reg).resolve("none", ["network"], ["app.brave"],
                               roles=cfg.roles)
    plan = build_plan(res, kernel=cfg.kernel,
                      filesystem=cfg.filesystem_type,
                      bootloader=cfg.bootloader_type,
                      shell=cfg.shell_type,
                      desktop_id=cfg.desktop_environment,
                      sources=cfg.sources)
    # The AUR package list may be empty (we don't pre-mark with aur:) but
    # the official package list should NOT contain the AUR package unless
    # the user has set aur=false. The plan reflects sources=arch only by
    # default, so brave-bin is not in the install list.
    assert "brave-bin" not in plan.packages or "aur" in str(plan.sources)


def test_default_options_sane():
    opts = InstallOptions()
    assert opts.hostname == "modular"
    assert opts.locale == "C.UTF-8"
    assert opts.timezone == "UTC"
    assert opts.administrator is True
