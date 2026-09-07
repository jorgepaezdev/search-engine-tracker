"""Look up where a URL appears in DuckDuckGo organic results for given keywords."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

RESULTS_PER_PAGE = 10
MAX_RESULTS = 50
MAX_PAGES = 5
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
DEBUG_LOG_PATH = "/Users/jorgepaez/serp-tracker/.cursor/debug-121916.log"

USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    ),
]


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "121916",
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


@dataclass(frozen=True)
class RankHit:
    keyword: str
    found: bool
    result_number: int | None
    page_number: int | None
    matched_url: str | None
    note: str


def parse_keywords(raw: str) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for part in raw.split(","):
        keyword = " ".join(part.split()).strip()
        if not keyword:
            continue
        key = keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(keyword)
    return keywords


def normalize_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("URL is required.")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid website URL, such as https://example.com.")
    return value


def host_of(url: str) -> str:
    candidate = url.strip()
    if candidate and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        candidate = "https://" + candidate
    parsed = urlparse(candidate)
    host = (parsed.netloc or "").lower()
    if "@" in host:
        host = host.split("@", 1)[1]
    if host.startswith("www."):
        host = host[4:]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


def url_matches_target(result_url: str, target_url: str) -> bool:
    result_host = host_of(result_url)
    target_host = host_of(target_url)
    if not result_host or not target_host:
        return False
    if result_host == target_host or result_host.endswith("." + target_host):
        return True
    if target_host.endswith("." + result_host):
        return True
    return False


def unwrap_ddg_href(href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    if query.get("uddg"):
        return unquote(query["uddg"][0])
    if parsed.scheme in {"http", "https"}:
        return href
    return None


def extract_organic_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a"):
        href = unwrap_ddg_href(anchor.get("href", ""))
        if not href:
            continue
        host = host_of(href)
        if not host or host.endswith("duckduckgo.com"):
            continue
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls


def page_for_result(result_number: int, per_page: int = RESULTS_PER_PAGE) -> int:
    return ((result_number - 1) // per_page) + 1


def format_rank(hit: RankHit) -> str:
    if not hit.found or hit.result_number is None or hit.page_number is None:
        return hit.note
    return f"Result #{hit.result_number}, page {hit.page_number}"


@dataclass(frozen=True)
class RankReport:
    url: str
    source: str
    notice: str | None
    results: list[RankHit]


def hit_from_urls(
    keyword: str,
    target_url: str,
    organic: list[str],
    engine_label: str = "DuckDuckGo",
) -> RankHit:
    for index, url in enumerate(organic, start=1):
        if url_matches_target(url, target_url):
            page_number = page_for_result(index)
            return RankHit(
                keyword=keyword,
                found=True,
                result_number=index,
                page_number=page_number,
                matched_url=url,
                note=f"Result #{index}, page {page_number}",
            )
    checked = len(organic)
    return RankHit(
        keyword=keyword,
        found=False,
        result_number=None,
        page_number=None,
        matched_url=None,
        note=f"Not found in the first {checked or RESULTS_PER_PAGE} {engine_label} results",
    )


def _headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://html.duckduckgo.com/",
    }


def _page_payload(keyword: str, page_index: int) -> dict[str, str]:
    payload = {"q": keyword, "kl": "us-en"}
    if page_index > 0:
        payload["s"] = str(10 + (page_index - 1) * 15)
    return payload


def fetch_duckduckgo_urls(keyword: str, max_results: int = MAX_RESULTS) -> list[str]:
    organic: list[str] = []
    seen: set[str] = set()
    with httpx.Client(timeout=httpx.Timeout(20.0), follow_redirects=True, headers=_headers()) as client:
        for page_index in range(MAX_PAGES):
            response = client.post(DUCKDUCKGO_HTML_URL, data=_page_payload(keyword, page_index))
            page_urls = extract_organic_urls(response.text)
            # #region agent log
            _debug_log(
                "A",
                "ranking.py:fetch_duckduckgo_urls",
                "Fetched DuckDuckGo HTML page",
                {
                    "keyword": keyword,
                    "page_index": page_index,
                    "status_code": response.status_code,
                    "html_len": len(response.text),
                    "page_url_count": len(page_urls),
                    "engine": "html.duckduckgo.com",
                },
            )
            # #endregion
            if response.status_code != 200 or not page_urls:
                if not organic:
                    raise RuntimeError(
                        "DuckDuckGo did not return search results. Try again in a moment."
                    )
                break
            for url in page_urls:
                if url in seen:
                    continue
                seen.add(url)
                organic.append(url)
                if len(organic) >= max_results:
                    return organic
            if page_index < MAX_PAGES - 1:
                time.sleep(0.4)
    return organic


def rank_with_duckduckgo(keyword: str, target_url: str, max_results: int = MAX_RESULTS) -> RankHit:
    organic: list[str] = []
    seen: set[str] = set()
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0), follow_redirects=True, headers=_headers()) as client:
            for page_index in range(MAX_PAGES):
                response = client.post(DUCKDUCKGO_HTML_URL, data=_page_payload(keyword, page_index))
                page_urls = extract_organic_urls(response.text)
                # #region agent log
                _debug_log(
                    "A",
                    "ranking.py:rank_with_duckduckgo",
                    "Fetched DuckDuckGo HTML page",
                    {
                        "keyword": keyword,
                        "page_index": page_index,
                        "status_code": response.status_code,
                        "html_len": len(response.text),
                        "page_url_count": len(page_urls),
                        "engine": "html.duckduckgo.com",
                    },
                )
                # #endregion
                if response.status_code != 200 or not page_urls:
                    if not organic:
                        raise RuntimeError(
                            "DuckDuckGo did not return search results. Try again in a moment."
                        )
                    break
                for url in page_urls:
                    if url in seen:
                        continue
                    seen.add(url)
                    organic.append(url)
                    if url_matches_target(url, target_url) or len(organic) >= max_results:
                        # #region agent log
                        _debug_log(
                            "C",
                            "ranking.py:rank_with_duckduckgo",
                            "Parsed DuckDuckGo organic URLs",
                            {
                                "keyword": keyword,
                                "organic_count": len(organic),
                                "first_host": host_of(organic[0]) if organic else None,
                            },
                        )
                        # #endregion
                        return hit_from_urls(keyword, target_url, organic, "DuckDuckGo")
                if page_index < MAX_PAGES - 1:
                    time.sleep(0.4)
    except Exception as exc:
        # #region agent log
        _debug_log(
            "A",
            "ranking.py:rank_with_duckduckgo",
            "DuckDuckGo lookup failed",
            {"keyword": keyword, "error_type": type(exc).__name__, "error": str(exc)[:300]},
        )
        # #endregion
        raise
    # #region agent log
    _debug_log(
        "C",
        "ranking.py:rank_with_duckduckgo",
        "Parsed DuckDuckGo organic URLs",
        {"keyword": keyword, "organic_count": len(organic), "first_host": host_of(organic[0]) if organic else None},
    )
    # #endregion
    return hit_from_urls(keyword, target_url, organic, "DuckDuckGo")


def lookup_ranks(keywords: Iterable[str], target_url: str) -> RankReport:
    target = normalize_url(target_url)
    hits: list[RankHit] = []
    for index, keyword in enumerate(keywords):
        if index:
            time.sleep(0.4)
        hits.append(rank_with_duckduckgo(keyword, target))
    return RankReport(url=target, source="duckduckgo", notice=None, results=hits)
