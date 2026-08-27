import pytest

from installer.installation import steps


def test_pacstrap_includes_packages():
    cmd = steps.pacstrap_command(["base", "linux"], root="/mnt")
    assert cmd[:4] == ["pacstrap", "-K", "/mnt", "base"]
    assert "linux" in cmd


def test_bootloader_systemd_boot():
    cmds = steps.bootloader_commands("systemd-boot")
    assert ["arch-chroot", "/mnt", "bootctl", "--esp-path=/boot",
            "install"] in cmds


def test_bootloader_grub_supported():
    cmds = steps.bootloader_commands("grub")
    joined = [" ".join(c) for c in cmds]
    assert any("grub-install" in j for j in joined)
    assert any("--efi-directory=/boot" in j for j in joined)
    assert any("grub-mkconfig" in j for j in joined)


def test_bootloader_unknown_rejected():
    with pytest.raises(ValueError):
        steps.bootloader_commands("lilo")


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
    username, password = marker["__stdin_user__"]
    assert (username, password) == ("alice", "supersecret99")


def test_user_creation_with_root_password():
    result = steps.user_commands("bob", "Bob B", "userpw",
                                 root_password="rootpw",
                                 administrator=True)
    marker = getattr(result, "marker", None)
    assert marker is not None
    assert marker["__stdin_root__"] == "rootpw"


def test_user_creation_includes_audio_group():
    result = steps.user_commands("carol", "Carol C", "pw",
                                 administrator=True)
    useradd = result[0]
    groups_arg = useradd[useradd.index("-G") + 1]
    assert "audio" in groups_arg
    assert "video" in groups_arg
    assert "wheel" in groups_arg


def test_user_creation_quotes_full_name():
    result = steps.user_commands("dave", "O'Brien; rm -rf /", "pw",
                                 administrator=True)
    for cmd in result:
        for arg in cmd:
            assert "rm -rf" not in arg or "'" in arg
        joined = " ".join(cmd)
        if "O'Brien" in joined or "rm -rf" in joined:
            # The full name must be shell-quoted, so the dangerous
            # substring cannot appear unquoted.
            assert "'" in joined


def test_user_rejects_bad_username():
    with pytest.raises(ValueError):
        steps.user_commands("Bad Name", "x", "pw")
    with pytest.raises(ValueError):
        steps.user_commands("", "x", "pw")


def test_timezone_and_hostname():
    tz = steps.set_timezone("Europe/Berlin")
    assert tz[0][3] == "-sf"
    hn = steps.set_hostname("mybox")
    assert isinstance(hn, list)
    assert len(hn) >= 1
    flat = " ".join(" ".join(c) for c in hn)
    assert "mybox" in flat


def test_set_keymap():
    cmds = steps.set_keymap("de-latin1")
    assert any("vconsole.conf" in " ".join(c) for c in cmds)


def test_configure_locale():
    cmds = steps.configure_locale("en_US.UTF-8")
    assert any("locale-gen" in c for c in cmds)


def test_localization_inputs_validated():
    with pytest.raises(ValueError):
        steps.set_timezone("../../etc/passwd")
    with pytest.raises(ValueError):
        steps.set_timezone("")
    with pytest.raises(ValueError):
        steps.configure_locale("en_US.UTF-8; rm -rf /")
    with pytest.raises(ValueError):
        steps.set_keymap("us && reboot")
    with pytest.raises(ValueError):
        steps.set_hostname("bad host; name")


def test_regenerate_initramfs():
    # -P (all presets): -p was deprecated in mkinitcpio v38 and removed later
    cmds = steps.regenerate_initramfs("linux-zen")
    assert ["arch-chroot", "/mnt", "mkinitcpio", "-P"] in cmds
    assert all("mkinitcpio" in " ".join(c) and "-p" not in c[3:]
               for c in cmds)


def test_systemd_boot_files_complete():
    files = steps.systemd_boot_files(
        kernel="linux", root_arg="PARTUUID=abcd-1234", ucode="intel-ucode")
    assert set(files) == {
        "/mnt/boot/loader/loader.conf",
        "/mnt/boot/loader/entries/arch.conf",
        "/mnt/boot/loader/entries/arch-fallback.conf",
    }
    entry = files["/mnt/boot/loader/entries/arch.conf"]
    assert "linux   /vmlinuz-linux" in entry
    assert "initrd  /intel-ucode.img" in entry
    assert "initrd  /initramfs-linux.img" in entry
    assert "options root=PARTUUID=abcd-1234 rw" in entry
    fallback = files["/mnt/boot/loader/entries/arch-fallback.conf"]
    assert "initramfs-linux-fallback.img" in fallback
    loader = files["/mnt/boot/loader/loader.conf"]
    assert "default   arch.conf" in loader


def test_systemd_boot_files_without_ucode():
    files = steps.systemd_boot_files(kernel="linux-lts",
                                     root_arg="/dev/sda2", ucode=None)
    entry = files["/mnt/boot/loader/entries/arch.conf"]
    assert "ucode" not in entry
    assert "vmlinuz-linux-lts" in entry
    assert "options root=/dev/sda2 rw" in entry


def test_systemd_boot_files_require_root_arg():
    with pytest.raises(ValueError):
        steps.systemd_boot_files(kernel="linux", root_arg="")


def test_export_configuration_path():
    files = steps.export_configuration("version: 0.1\n", target_root="/mnt")
    assert list(files) == ["/mnt/etc/modular/modular.yaml"]


def test_export_rejects_path_outside_root():
    with pytest.raises(ValueError):
        steps.export_configuration("x: y", target_root="/mnt",
                                   target_path="/etc/shadow")


def test_is_chroot_ready():
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        assert not steps.is_chroot_ready(td)
        os.makedirs(os.path.join(td, "etc"))
        open(os.path.join(td, "etc", "os-release"), "w").close()
        os.makedirs(os.path.join(td, "usr", "bin"))
        os.makedirs(os.path.join(td, "bin"))
        open(os.path.join(td, "bin", "bash"), "w").close()
        assert steps.is_chroot_ready(td)
