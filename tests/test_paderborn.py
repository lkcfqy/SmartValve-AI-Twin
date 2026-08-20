from __future__ import annotations

import json
from hashlib import sha256

import pytest

from smartvalve.data import paderborn


def test_archive_list_is_complete_and_unique() -> None:
    assert len(paderborn.ARCHIVE_NAMES) == 32
    assert len(set(paderborn.ARCHIVE_NAMES)) == 32
    assert sum(name.startswith("K0") for name in paderborn.ARCHIVE_NAMES) == 6
    assert sum(name.startswith("KA") for name in paderborn.ARCHIVE_NAMES) == 12
    assert sum(name.startswith("KB") for name in paderborn.ARCHIVE_NAMES) == 3
    assert sum(name.startswith("KI") for name in paderborn.ARCHIVE_NAMES) == 11


def test_official_metadata_covers_every_locked_archive_once() -> None:
    codes = tuple(item.code for item in paderborn.BEARING_METADATA)
    archive_codes = tuple(name.removesuffix(".rar") for name in paderborn.ARCHIVE_NAMES)

    assert codes == archive_codes
    assert len(set(codes)) == 32
    counts = {
        label: sum(item.primary_label == label for item in paderborn.BEARING_METADATA)
        for label in ("healthy", "outer", "inner", "compound")
    }
    assert counts == {"healthy": 6, "outer": 12, "inner": 11, "compound": 3}
    assert len(paderborn.PRIMARY_BEARING_CODES) == 29
    assert paderborn.COMPOUND_BEARING_CODES == ("KB23", "KB24", "KB27")


def test_official_operating_settings_change_one_factor_from_reference() -> None:
    settings = paderborn.OPERATING_SETTINGS
    reference = settings[0]

    assert len(settings) == 4
    assert len({setting.code for setting in settings}) == 4
    assert (reference.speed_rpm, reference.torque_nm, reference.radial_force_n) == (
        1500,
        0.7,
        1000,
    )
    for setting in settings[1:]:
        differences = sum(
            left != right
            for left, right in zip(
                (reference.speed_rpm, reference.torque_nm, reference.radial_force_n),
                (setting.speed_rpm, setting.torque_nm, setting.radial_force_n),
                strict=True,
            )
        )
        assert differences == 1


def test_content_range_total_is_strict() -> None:
    assert paderborn._content_range_total("bytes 50-99/100") == 100
    assert paderborn._content_range_total(None) is None
    assert paderborn._content_range_total("invalid") is None
    assert paderborn._content_range_total("bytes */*") is None


def test_verify_cached_lock_checks_digest(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "paderborn"
    cache.mkdir()
    payload = b"sealed archive bytes"
    entries = []
    for name in paderborn.ARCHIVE_NAMES:
        (cache / name).write_bytes(payload)
        entries.append(
            {
                "filename": name,
                "bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        )
    lock = {
        "acquisition_version": paderborn.ACQUISITION_VERSION,
        "status": "test lock",
        "archive_count": 32,
        "total_bytes": len(payload) * 32,
        "archives": entries,
    }
    lock_path = cache / "archive_lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(paderborn, "paderborn_cache_directory", lambda: cache)

    assert paderborn.verify_cached_lock(lock_path)["archive_count"] == 32
    (cache / paderborn.ARCHIVE_NAMES[0]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs from lock"):
        paderborn.verify_cached_lock(lock_path)
