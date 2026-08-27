import pytest

from engine.profiles import Profile, ProfileRegistry


def test_profile_from_minimal_dict():
    p = Profile.from_dict({"id": "x.y", "name": "Y", "category": "base"})
    assert p.packages == ()
    assert p.services.enable == ()


def test_profile_missing_id_raises():
    with pytest.raises(Exception):
        Profile.from_dict({"name": "NoId", "category": "base"})


def test_registry_duplicate_ids_rejected(tmp_path):
    cat = tmp_path / "base"
    cat.mkdir()
    data = "id: base.dup\nname: Dup\ncategory: base\n"
    (cat / "a.yaml").write_text(data)
    (cat / "b.yaml").write_text(data)
    reg = ProfileRegistry()
    with pytest.raises(Exception):
        reg.load_directory(str(tmp_path))
