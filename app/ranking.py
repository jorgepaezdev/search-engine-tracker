"""Look up where a URL appears in DuckDuckGo or Bing organic results for given keywords."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, Literal
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

RESULTS_PER_PAGE = 10
MAX_RESULTS = 50
MAX_PAGES = 5
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
BING_SEARCH_URL = "https://www.bing.com/search"

SearchEngine = Literal["duckduckgo", "bing"]
ENGINE_LABELS = {
    "duckduckgo": "DuckDuckGo",
    "bing": "Bing",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


@dataclass(frozen=True)
class RankHit:
    keyword: str
    found: bool
    result_number: int | None
    page_number: int | None
    matched_url: str | None
    note: str


def parse_engine(raw: str) -> SearchEngine:
    value = (raw or "").strip().lower()
    if value in {"duckduckgo", "ddg", "duck"}:
        return "duckduckgo"
    if value == "bing":
        return "bing"
    raise ValueError("Choose DuckDuckGo or Bing.")


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


def extract_bing_rss_urls(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1].lower()
        if tag != "item":
            continue
        link = ""
        for child in item:
            child_tag = child.tag.rsplit("}", 1)[-1].lower()
            if child_tag == "link":
                link = (child.text or "").strip()
                break
        if not link:
            continue
        host = host_of(link)
        if not host or host.endswith("bing.com") or host.endswith("microsoft.com"):
            continue
        if link in seen:
            continue
        seen.add(link)
        urls.append(link)
    return urls


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


def next_page_payload(html: str) -> dict[str, str] | None:
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.select("form"):
        names = {inp.get("name") for inp in form.select("input[name]")}
        if "s" in names and "vqd" in names:
            payload: dict[str, str] = {}
            for inp in form.select("input[name]"):
                if (inp.get("type") or "").lower() == "submit":
                    continue
                payload[str(inp.get("name"))] = inp.get("value") or ""
            return payload
    return None


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


def _headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
    }


class DuckDuckGoClient:
    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
            headers=_headers(DUCKDUCKGO_HTML_URL),
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "DuckDuckGoClient":
        self.warm()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def warm(self) -> None:
        self.client.get(DUCKDUCKGO_HTML_URL)

    def _search(self, data: dict[str, str]) -> httpx.Response:
        response = self.client.post(DUCKDUCKGO_HTML_URL, data=data)
        if response.status_code == 202 or not extract_organic_urls(response.text):
            self.warm()
            time.sleep(0.4)
            response = self.client.post(DUCKDUCKGO_HTML_URL, data=data)
        return response

    def rank(self, keyword: str, target_url: str, max_results: int = MAX_RESULTS) -> RankHit:
        organic: list[str] = []
        seen: set[str] = set()
        payload: dict[str, str] | None = {"q": keyword, "kl": "us-en"}

        for _page_index in range(MAX_PAGES):
            if payload is None:
                break
            response = self._search(payload)
            page_urls = extract_organic_urls(response.text)
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
                    return hit_from_urls(keyword, target_url, organic, "DuckDuckGo")
            payload = next_page_payload(response.text)
            if payload is not None:
                time.sleep(0.4)
        return hit_from_urls(keyword, target_url, organic, "DuckDuckGo")


def rank_with_duckduckgo(keyword: str, target_url: str, max_results: int = MAX_RESULTS) -> RankHit:
    with DuckDuckGoClient() as client:
        return client.rank(keyword, target_url, max_results=max_results)


class BingClient:
    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
            headers=_headers("https://www.bing.com/"),
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "BingClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def rank(self, keyword: str, target_url: str, max_results: int = MAX_RESULTS) -> RankHit:
        organic: list[str] = []
        seen: set[str] = set()
        first = 1

        for _page_index in range(MAX_PAGES):
            remaining = max_results - len(organic)
            if remaining <= 0:
                break
            response = self.client.get(
                BING_SEARCH_URL,
                params={
                    "q": keyword,
                    "format": "rss",
                    "count": str(min(RESULTS_PER_PAGE, remaining)),
                    "first": str(first),
                },
            )
            page_urls = extract_bing_rss_urls(response.text)
            if response.status_code != 200 or not page_urls:
                if not organic:
                    raise RuntimeError(
                        "Bing did not return search results. Try again in a moment."
                    )
                break
            new_on_page = 0
            for url in page_urls:
                if url in seen:
                    continue
                seen.add(url)
                organic.append(url)
                new_on_page += 1
                if url_matches_target(url, target_url) or len(organic) >= max_results:
                    return hit_from_urls(keyword, target_url, organic, "Bing")
            if new_on_page == 0:
                break
            first += new_on_page
            time.sleep(0.3)
        return hit_from_urls(keyword, target_url, organic, "Bing")


def rank_with_bing(keyword: str, target_url: str, max_results: int = MAX_RESULTS) -> RankHit:
    with BingClient() as client:
        return client.rank(keyword, target_url, max_results=max_results)


def lookup_ranks(
    keywords: Iterable[str],
    target_url: str,
    engine: str = "duckduckgo",
) -> RankReport:
    selected = parse_engine(engine)
    target = normalize_url(target_url)
    keyword_list = list(keywords)
    hits: list[RankHit] = []
    client_cls = BingClient if selected == "bing" else DuckDuckGoClient
    with client_cls() as client:
        for index, keyword in enumerate(keyword_list):
            if index:
                time.sleep(0.5)
            hits.append(client.rank(keyword, target))
    return RankReport(url=target, source=selected, notice=None, results=hits)
