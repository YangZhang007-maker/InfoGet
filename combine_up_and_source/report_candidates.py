"""Deterministic candidate extraction, scoring, and deduplication."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .report_models import CandidateItem


_TRACKING_PARAMETERS = {"spm", "from", "source", "ref", "referrer"}


class ReportCandidateBuilder:
    TITLE_SIMILARITY_THRESHOLD = 0.92

    def build(self, snapshot: dict[str, Any], amount: int) -> list[CandidateItem]:
        result = snapshot.get("result", snapshot)
        keywords = self._clean_keywords(result.get("keywords", []))
        reasons = self._source_reasons(result)
        raw_items: list[dict[str, Any]] = []

        for batch in result.get("batches", []):
            for source in batch.get("results", []):
                source_name = str(
                    source.get("matched_platform")
                    or source.get("source_name")
                    or self._hostname(source.get("source_url", ""))
                    or "未知来源"
                ).strip()
                source_key = (
                    self._hostname(source.get("source_url", ""))
                    or source_name.casefold()
                )
                for item in source.get("items", []):
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    normalized_url = self.normalize_url(url)
                    if not title or not normalized_url:
                        continue
                    summary = str(item.get("summary") or item.get("desc") or "").strip()
                    raw_items.append({
                        "title": title,
                        "url": url,
                        "normalized_url": normalized_url,
                        "source_name": source_name,
                        "source_key": source_key,
                        "summary": summary,
                        "hot": str(item.get("hot") or "").strip(),
                        "existing_relevance": self._bounded_int(item.get("relevance")),
                        "match_type": str(item.get("match_type") or "").strip(),
                        "reason": reasons.get(source_name.casefold(), ""),
                    })

        max_heat = max((self._parse_heat(item["hot"]) for item in raw_items), default=0.0)
        candidates = [self._to_candidate(item, keywords, max_heat) for item in raw_items]
        candidates = self._deduplicate_urls(candidates)
        candidates = self._deduplicate_titles(candidates)
        candidates.sort(key=lambda item: (-item.rule_score, item.item_id))
        return candidates[:min(max(int(amount), 1) * 3, 60)]

    @staticmethod
    def normalize_url(value: str) -> str:
        try:
            parsed = urlsplit(str(value or "").strip())
        except ValueError:
            return ""
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"} or not parsed.hostname:
            return ""
        hostname = parsed.hostname.lower()
        try:
            port = parsed.port
        except ValueError:
            return ""
        if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.casefold()
            if lowered.startswith("utm_") or lowered in _TRACKING_PARAMETERS:
                continue
            query.append((key, value))
        query.sort(key=lambda pair: (pair[0], pair[1]))
        return urlunsplit((scheme, netloc, path, urlencode(query), ""))

    def _to_candidate(
        self,
        raw: dict[str, Any],
        keywords: list[str],
        max_heat: float,
    ) -> CandidateItem:
        title_matches = self._match_ratio(raw["title"], keywords)
        summary_matches = self._match_ratio(raw["summary"], keywords)
        reason_matches = self._match_ratio(raw["reason"], keywords)
        heat_value = self._parse_heat(raw["hot"])
        heat_score = round(100 * heat_value / max_heat) if max_heat > 0 else 0
        quality_score = self._quality_score(raw)
        score = round(
            title_matches * 30
            + summary_matches * 20
            + raw["existing_relevance"] * 0.20
            + reason_matches * 10
            + heat_score * 0.10
            + quality_score * 0.10
        )
        normalized_title = self._normalize_title(raw["title"])
        material = f'{raw["normalized_url"]}\n{normalized_title}'.encode("utf-8")
        item_id = hashlib.sha256(material).hexdigest()[:32]
        return CandidateItem(
            item_id=item_id,
            title=raw["title"][:500],
            url=raw["url"][:4000],
            normalized_url=raw["normalized_url"][:4000],
            source_name=raw["source_name"][:200],
            source_key=raw["source_key"][:300],
            summary=raw["summary"][:3000],
            hot=raw["hot"][:200],
            existing_relevance=raw["existing_relevance"],
            match_type=raw["match_type"][:200],
            rule_score=max(0, min(score, 100)),
            quality_score=quality_score,
            heat_score=heat_score,
        )

    @staticmethod
    def _quality_score(raw: dict[str, Any]) -> int:
        score = 20
        if raw["summary"]:
            score += min(40, 10 + len(raw["summary"]) // 10)
        if raw["source_name"] and raw["source_name"] != "未知来源":
            score += 20
        if raw["hot"]:
            score += 10
        if raw["match_type"]:
            score += 10
        return min(score, 100)

    @staticmethod
    def _parse_heat(value: str) -> float:
        text = str(value or "").replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return 0.0
        number = float(match.group(1))
        if "亿" in text:
            number *= 100_000_000
        elif "万" in text or "w" in text.casefold():
            number *= 10_000
        elif "千" in text or "k" in text.casefold():
            number *= 1_000
        return number if math.isfinite(number) else 0.0

    @staticmethod
    def _bounded_int(value: Any) -> int:
        try:
            return max(0, min(int(float(value or 0)), 100))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _clean_keywords(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(
            str(value).strip() for value in values if str(value).strip()
        ))

    @staticmethod
    def _match_ratio(text: str, keywords: list[str]) -> float:
        if not text or not keywords:
            return 0.0
        haystack = unicodedata.normalize("NFKC", text).casefold()
        matches = sum(
            unicodedata.normalize("NFKC", keyword).casefold() in haystack
            for keyword in keywords
        )
        return matches / len(keywords)

    @staticmethod
    def _source_reasons(result: dict[str, Any]) -> dict[str, str]:
        reasons: dict[str, list[str]] = {}
        sources = list(result.get("source_inputs", []))
        recommendation = result.get("recommendation", {})
        sources.extend(recommendation.get("bloggers", []))
        sources.extend(recommendation.get("platforms", []))
        for source in sources:
            name = str(source.get("name") or "").strip().casefold()
            reason = str(source.get("reason") or "").strip()
            if name and reason:
                reasons.setdefault(name, []).append(reason)
        return {key: " ".join(values) for key, values in reasons.items()}

    @staticmethod
    def _hostname(value: str) -> str:
        try:
            return (urlsplit(str(value or "")).hostname or "").lower()
        except ValueError:
            return ""

    @staticmethod
    def _normalize_title(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return "".join(character for character in normalized if character.isalnum())

    @staticmethod
    def _deduplicate_urls(candidates: list[CandidateItem]) -> list[CandidateItem]:
        selected: dict[str, CandidateItem] = {}
        for candidate in candidates:
            previous = selected.get(candidate.normalized_url)
            rank = (candidate.rule_score, candidate.quality_score, len(candidate.summary))
            previous_rank = (
                previous.rule_score,
                previous.quality_score,
                len(previous.summary),
            ) if previous else (-1, -1, -1)
            if previous is None or rank > previous_rank:
                selected[candidate.normalized_url] = candidate
        return list(selected.values())

    def _deduplicate_titles(self, candidates: list[CandidateItem]) -> list[CandidateItem]:
        ordered = sorted(
            candidates,
            key=lambda item: (-item.rule_score, -item.quality_score, item.item_id),
        )
        selected: list[CandidateItem] = []
        normalized_titles: list[str] = []
        for candidate in ordered:
            title = self._normalize_title(candidate.title)
            if any(
                SequenceMatcher(None, title, existing).ratio()
                >= self.TITLE_SIMILARITY_THRESHOLD
                for existing in normalized_titles
            ):
                continue
            selected.append(candidate)
            normalized_titles.append(title)
        return selected
