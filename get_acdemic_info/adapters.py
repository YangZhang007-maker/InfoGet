"""Official API adapters for common academic sources."""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import List
from urllib.parse import quote_plus, urlparse

from .http_client import PoliteHttpClient
from .models import AcademicArticle, AcademicSearchRequest
from .utils import clean_text

logger = logging.getLogger(__name__)


class AcademicAdapter(ABC):
    name = "Academic source"
    strategy = "official_api"

    def __init__(self, client: PoliteHttpClient) -> None:
        self.client = client

    @abstractmethod
    def search(self, request: AcademicSearchRequest) -> List[AcademicArticle]:
        raise NotImplementedError


class ArxivAdapter(AcademicAdapter):
    name = "arXiv"

    def search(self, request: AcademicSearchRequest) -> List[AcademicArticle]:
        query = " OR ".join(f'all:"{keyword}"' for keyword in request.keywords)
        response = self.client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": query,
                "start": 0,
                "max_results": min(max(request.max_results * 3, 30), 100),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            accept="application/atom+xml",
        )
        root = ET.fromstring(response.content)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        articles = []
        for entry in root.findall("atom:entry", namespace):
            entry_url = _xml_text(entry, "atom:id", namespace)
            articles.append(
                AcademicArticle(
                    title=clean_text(_xml_text(entry, "atom:title", namespace)),
                    url=entry_url,
                    authors=[
                        clean_text(_xml_text(author, "atom:name", namespace))
                        for author in entry.findall("atom:author", namespace)
                    ],
                    published_at=_xml_text(entry, "atom:published", namespace),
                    abstract=clean_text(_xml_text(entry, "atom:summary", namespace)),
                    source=self.name,
                )
            )
        return articles


class PubMedAdapter(AcademicAdapter):
    name = "PubMed"

    def search(self, request: AcademicSearchRequest) -> List[AcademicArticle]:
        term = " OR ".join(f'"{keyword}"[Title/Abstract]' for keyword in request.keywords)
        term = f"({term})"
        if request.time_range_days:
            start = (datetime.now(timezone.utc) - timedelta(days=request.time_range_days)).strftime("%Y/%m/%d")
            term += f" AND ({start}:3000[dp])"
        search_response = self.client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": min(max(request.max_results * 3, 30), 100),
                "sort": "pub date",
                "tool": "daily-hot-academic",
            },
            accept="application/json",
        )
        ids = search_response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        fetch_response = self.client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
            accept="application/xml",
        )
        root = ET.fromstring(fetch_response.content)
        articles = []
        for record in root.findall(".//PubmedArticle"):
            pmid = _element_text(record.find(".//PMID"))
            title = "".join(record.find(".//ArticleTitle").itertext()) if record.find(".//ArticleTitle") is not None else ""
            abstract = " ".join(
                "".join(node.itertext()) for node in record.findall(".//Abstract/AbstractText")
            )
            authors = []
            for author in record.findall(".//Author"):
                collective = _element_text(author.find("CollectiveName"))
                person = " ".join(
                    part for part in (
                        _element_text(author.find("ForeName")),
                        _element_text(author.find("LastName")),
                    ) if part
                )
                if collective or person:
                    authors.append(collective or person)
            date_node = record.find(".//ArticleDate")
            if date_node is None:
                date_node = record.find(".//PubDate")
            published = _pubmed_date(date_node)
            articles.append(
                AcademicArticle(
                    title=clean_text(title),
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    authors=authors,
                    published_at=published,
                    abstract=clean_text(abstract),
                    source=self.name,
                )
            )
        return articles


class OpenAlexAdapter(AcademicAdapter):
    name = "OpenAlex"
    strategy = "official_api_alternative"

    def search(self, request: AcademicSearchRequest) -> List[AcademicArticle]:
        query = " ".join(request.keywords)
        filters = []
        if request.time_range_days:
            start = (datetime.now(timezone.utc) - timedelta(days=request.time_range_days)).date()
            filters.append(f"from_publication_date:{start.isoformat()}")
        response = self.client.get(
            "https://api.openalex.org/works",
            params={
                "search": query,
                "filter": ",".join(filters) if filters else None,
                "sort": "cited_by_count:desc",
                "per-page": min(max(request.max_results * 3, 30), 100),
            },
            accept="application/json",
        )
        articles = []
        for work in response.json().get("results", []):
            location = work.get("primary_location") or {}
            url = location.get("landing_page_url") or work.get("doi") or work.get("id", "")
            authors = [
                item.get("author", {}).get("display_name", "")
                for item in work.get("authorships", [])
                if item.get("author", {}).get("display_name")
            ]
            articles.append(
                AcademicArticle(
                    title=clean_text(work.get("display_name", "")),
                    url=url,
                    authors=authors,
                    published_at=work.get("publication_date"),
                    abstract=_decode_openalex_abstract(work.get("abstract_inverted_index")),
                    citations=work.get("cited_by_count"),
                    source=self.name,
                )
            )
        return articles


def select_adapter(source_url: str, client: PoliteHttpClient) -> AcademicAdapter | None:
    hostname = (urlparse(source_url).hostname or "").lower()
    if hostname == "arxiv.org" or hostname.endswith(".arxiv.org"):
        return ArxivAdapter(client)
    if "pubmed.ncbi.nlm.nih.gov" in hostname or hostname.endswith("ncbi.nlm.nih.gov"):
        return PubMedAdapter(client)
    if "scholar.google." in hostname or hostname == "openalex.org" or hostname.endswith(".openalex.org"):
        return OpenAlexAdapter(client)
    return None


def _xml_text(element: ET.Element, path: str, namespace: dict) -> str:
    node = element.find(path, namespace)
    return node.text.strip() if node is not None and node.text else ""


def _element_text(element: ET.Element | None) -> str:
    return element.text.strip() if element is not None and element.text else ""


def _pubmed_date(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    year = _element_text(element.find("Year"))
    month = _element_text(element.find("Month")) or "01"
    day = _element_text(element.find("Day")) or "01"
    if not year:
        medline = _element_text(element.find("MedlineDate"))
        match = re.search(r"\d{4}", medline)
        return match.group() if match else None
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    return f"{year}-{month_map.get(month, month.zfill(2))}-{day.zfill(2)}"


def _decode_openalex_abstract(index: dict | None) -> str:
    if not index:
        return ""
    positions = sorted(
        (position, word)
        for word, word_positions in index.items()
        for position in word_positions
    )
    return " ".join(word for _, word in positions)
