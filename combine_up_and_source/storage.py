"""Persistent snapshots and generated reports for combined discovery."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


class SnapshotNotFoundError(ValueError):
    """Raised when a discovery snapshot does not exist."""


class SnapshotCorruptError(ValueError):
    """Raised when a discovery snapshot cannot be trusted."""


class DiscoveryStorage:
    DISCOVERY_SCHEMA_VERSION = 1
    _REPORT_ID_PATTERN = re.compile(r"[a-f0-9]{32}")

    def __init__(self, data_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self.data_dir = data_dir or project_root / "data" / "combined_discovery"

    @staticmethod
    def _safe_discovery_id(value: str) -> str:
        try:
            parsed = UUID(str(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("无效的智能发现 ID") from exc
        return str(parsed)

    @classmethod
    def _safe_report_id(cls, value: str) -> str:
        normalized = str(value or "").lower()
        if not cls._REPORT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("无效的报告 ID")
        return normalized

    def save_discovery(self, result: dict[str, Any]) -> str:
        if not isinstance(result, dict):
            raise ValueError("智能发现结果格式无效")
        discovery_id = str(uuid4())
        snapshot_dir = self.data_dir / discovery_id
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        payload = {
            "schema_version": self.DISCOVERY_SCHEMA_VERSION,
            "discovery_id": discovery_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "result": result,
        }
        self._write_json(snapshot_dir / "discovery.json", payload)
        return discovery_id

    def load_discovery(self, discovery_id: str) -> dict[str, Any]:
        safe_id = self._safe_discovery_id(discovery_id)
        path = self.data_dir / safe_id / "discovery.json"
        if not path.is_file():
            raise SnapshotNotFoundError("智能发现快照不存在")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotCorruptError("智能发现快照格式损坏") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("discovery_id") != safe_id
            or payload.get("status") != "completed"
            or not isinstance(payload.get("result"), dict)
        ):
            raise SnapshotCorruptError("智能发现快照格式无效")
        if payload.get("schema_version") != self.DISCOVERY_SCHEMA_VERSION:
            raise SnapshotCorruptError("智能发现快照版本不受支持")
        try:
            created_at = datetime.fromisoformat(str(payload.get("created_at") or ""))
        except ValueError as exc:
            raise SnapshotCorruptError("智能发现快照创建时间无效") from exc
        if created_at.tzinfo is None:
            raise SnapshotCorruptError("智能发现快照创建时间无效")
        return payload

    def report_id(
        self,
        discovery_id: str,
        amount: int,
        schema_version: int,
        variant: str = "default",
    ) -> str:
        safe_id = self._safe_discovery_id(discovery_id)
        material = f"{safe_id}:{int(amount)}:{int(schema_version)}:{variant}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()[:32]

    def save_report(
        self,
        discovery_id: str,
        report_id: str,
        payload: dict[str, Any],
        markdown: str,
    ) -> None:
        safe_discovery_id = self._safe_discovery_id(discovery_id)
        safe_report_id = self._safe_report_id(report_id)
        if self.load_report(safe_discovery_id, safe_report_id) is not None:
            return
        reports_dir = self.data_dir / safe_discovery_id / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_dir = reports_dir / safe_report_id
        temporary_dir = reports_dir / f".{safe_report_id}.{uuid4().hex}.tmp"
        temporary_dir.mkdir()
        try:
            self._write_json(temporary_dir / "report.json", payload)
            self._write_text(temporary_dir / "report.md", markdown)
            if report_dir.exists():
                if self.load_report(safe_discovery_id, safe_report_id) is not None:
                    return
                shutil.rmtree(report_dir)
            try:
                temporary_dir.replace(report_dir)
            except FileExistsError:
                if self.load_report(safe_discovery_id, safe_report_id) is None:
                    raise
        finally:
            if temporary_dir.exists():
                shutil.rmtree(temporary_dir)

    def load_report(self, discovery_id: str, report_id: str) -> dict[str, Any] | None:
        safe_discovery_id = self._safe_discovery_id(discovery_id)
        safe_report_id = self._safe_report_id(report_id)
        report_dir = self.data_dir / safe_discovery_id / "reports" / safe_report_id
        json_path = report_dir / "report.json"
        markdown_path = report_dir / "report.md"
        if not json_path.is_file() or not markdown_path.is_file():
            return None
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return {**payload, "markdown": markdown}

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        DiscoveryStorage._write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
