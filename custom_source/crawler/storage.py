"""Persist crawler plans and run results as reviewable JSON files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class CrawlerStorage:
    def __init__(self, data_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.data_dir = data_dir or project_root / "data" / "custom_crawler"
        self.plan_dir = self.data_dir / "plans"

    @staticmethod
    def _safe_id(value: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{32}", value):
            raise ValueError("无效的分析 ID")
        return value

    def save_plan(self, analysis_id: str, payload: dict[str, Any]) -> Path:
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        path = self.plan_dir / f"{self._safe_id(analysis_id)}.json"
        self._write_json(path, payload)
        return path

    def load_plan(self, analysis_id: str) -> dict[str, Any]:
        path = self.plan_dir / f"{self._safe_id(analysis_id)}.json"
        if not path.is_file():
            raise ValueError("分析计划不存在或已失效，请重新分析")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("分析计划格式无效")
        return data

    def save_result(self, run_id: str, payload: dict[str, Any]) -> Path:
        run_dir = self.data_dir / self._safe_id(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "results.json"
        self._write_json(path, payload)
        return path

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(path)

