import json

import pytest

from combine_up_and_source.storage import (
    DiscoveryStorage,
    SnapshotCorruptError,
    SnapshotNotFoundError,
)


def test_save_and_load_immutable_discovery(tmp_path):
    storage = DiscoveryStorage(tmp_path)

    discovery_id = storage.save_discovery({"query": "机器学习", "batches": []})
    snapshot = storage.load_discovery(discovery_id)

    assert snapshot["schema_version"] == 1
    assert snapshot["status"] == "completed"
    assert snapshot["discovery_id"] == discovery_id
    assert snapshot["result"]["query"] == "机器学习"
    assert "discovery_id" not in snapshot["result"]


def test_rejects_invalid_or_missing_discovery_id(tmp_path):
    storage = DiscoveryStorage(tmp_path)

    with pytest.raises(ValueError, match="无效"):
        storage.load_discovery("../../etc/passwd")
    with pytest.raises(SnapshotNotFoundError, match="不存在"):
        storage.load_discovery("00000000-0000-4000-8000-000000000000")


def test_rejects_corrupt_snapshot(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = "00000000-0000-4000-8000-000000000000"
    snapshot_dir = tmp_path / discovery_id
    snapshot_dir.mkdir()
    (snapshot_dir / "discovery.json").write_text("[]", encoding="utf-8")

    with pytest.raises(SnapshotCorruptError, match="格式"):
        storage.load_discovery(discovery_id)


def test_rejects_unsupported_or_malformed_snapshot_envelope(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery({"query": "AI", "batches": []})
    snapshot_path = tmp_path / discovery_id / "discovery.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    snapshot["schema_version"] = 99
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(SnapshotCorruptError, match="版本"):
        storage.load_discovery(discovery_id)

    snapshot["schema_version"] = 1
    snapshot["created_at"] = "not-a-date"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(SnapshotCorruptError, match="时间"):
        storage.load_discovery(discovery_id)


def test_report_id_is_stable_and_complete_report_is_reused(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery({"query": "AI", "batches": []})

    first = storage.report_id(discovery_id, amount=10, schema_version=1)
    second = storage.report_id(discovery_id, amount=10, schema_version=1)
    assert first == second
    assert len(first) == 32

    storage.save_report(discovery_id, first, {"report_id": first}, "# AI")
    cached = storage.load_report(discovery_id, first)
    assert cached == {"report_id": first, "markdown": "# AI"}


def test_incomplete_report_is_not_a_cache_hit(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery({"query": "AI", "batches": []})
    report_id = storage.report_id(discovery_id, amount=5, schema_version=1)
    report_dir = tmp_path / discovery_id / "reports" / report_id
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps({"report_id": report_id}), encoding="utf-8"
    )

    assert storage.load_report(discovery_id, report_id) is None


def test_saving_report_does_not_modify_discovery_snapshot(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery({"query": "AI", "batches": []})
    snapshot_path = tmp_path / discovery_id / "discovery.json"
    before = snapshot_path.read_bytes()
    report_id = storage.report_id(discovery_id, amount=5, schema_version=1)

    storage.save_report(discovery_id, report_id, {"report_id": report_id}, "# AI")

    assert snapshot_path.read_bytes() == before


def test_rejects_unsafe_report_id(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery({"query": "AI", "batches": []})

    with pytest.raises(ValueError, match="无效"):
        storage.load_report(discovery_id, "../outside")
