"""Atomic on-disk storage for one cross-platform ranking per day."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .models import DailyTopResponse

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DailyTopStorage:
    def __init__(self, data_root: str | Path | None = None) -> None:
        root = Path(
            data_root
            or os.getenv("DAILY_HOT_DATA_DIR")
            or Path(__file__).resolve().parents[1] / "data"
        )
        self.root = root / "daily_info"

    def load(self, date_key: str) -> DailyTopResponse | None:
        path = self._path(date_key)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            result = DailyTopResponse.model_validate(payload)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if result.schema_version != 1 or result.date != date_key:
            return None
        return result

    def save(self, response: DailyTopResponse) -> Path:
        destination = self._path(response.date)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = response.model_dump(mode="json")
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{response.date}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return destination

    def _path(self, date_key: str) -> Path:
        if not DATE_RE.fullmatch(date_key):
            raise ValueError("Invalid daily snapshot date")
        return self.root / f"{date_key}.json"
