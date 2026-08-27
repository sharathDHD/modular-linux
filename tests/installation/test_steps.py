import pytest

from installer.installation import steps


def test_pacstrap_includes_packages():
    cmd = steps.pacstrap_command(["base", "linux"], root="/mnt")
    assert cmd[:4] == ["pacstrap", "-K", "/mnt", "base"]
    assert "linux" in cmd


def test_bootloader_systemd_boot():
    cmds = steps.bootloader_commands("systemd-boot")
    assert ["arch-chroot", "/mnt", "bootctl", "install"] in cmds
    with pytest.raises(ValueError):
        steps.bootloader_commands("grub")


def test_service_units_get_suffix():
    assert steps.enable_service_command("sddm")[-1] == "sddm.service"
    assert steps.enable_service_command("NetworkManager")[-1] == \
        "NetworkManager.service"


def test_user_creation_password_not_in_argv():
    result = steps.user_commands("alice", "Alice A", "supersecret99",
                                 administrator=True)
    for cmd in result:
        for arg in cmd:
            assert "supersecret99" not in arg
        joined = " ".join(cmd)
        assert "supersecret99" not in joined
    marker = getattr(result, "marker", None)
    assert marker is not None
    username, password = marker["__stdin_password__"]
    assert (username, password) == ("alice", "supersecret99")


def test_timezone_and_hostname():
    tz = steps.set_timezone("Europe/Berlin")
    assert tz[0][3] == "-sf"
    hosts = steps.set_hostname("mybox")
    assert "mybox" in hosts["/mnt/etc/hosts"]


def test_export_configuration_path():
    files = steps.export_configuration("version: 0.1\n", target_root="/mnt")
    assert list(files) == ["/mnt/etc/modular/modular.yaml"]
