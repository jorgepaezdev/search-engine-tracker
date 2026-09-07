from app.ranking import (
    extract_organic_urls,
    format_rank,
    hit_from_urls,
    page_for_result,
    parse_keywords,
    url_matches_target,
    RankHit,
    normalize_url,
    host_of,
    lookup_ranks,
)


def test_parse_keywords_splits_and_dedupes():
    assert parse_keywords("  python, FastAPI, python, , uvicorn ") == [
        "python",
        "FastAPI",
        "uvicorn",
    ]


def test_normalize_url_adds_https():
    assert normalize_url("example.com/path") == "https://example.com/path"


def test_host_strips_www():
    assert host_of("https://www.Example.com:443/foo") == "example.com"


def test_url_match_allows_subdomains():
    assert url_matches_target("https://docs.python.org/3/", "https://python.org")
    assert url_matches_target("https://www.python.org/", "python.org")
    assert not url_matches_target("https://notpython.org", "https://python.org")


def test_extract_organic_urls_from_duckduckgo_html():
    html = """
    <html><body>
      <a class="result__a" href="https://www.python.org/">Python</a>
      <a class="result__a" href="https://docs.python.org/3/tutorial/">Tutorial</a>
      <a class="result__a" href="https://html.duckduckgo.com/html/">DDG</a>
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Ffastapi.tiangolo.com%2F">FastAPI</a>
    </body></html>
    """
    urls = extract_organic_urls(html)
    assert urls == [
        "https://www.python.org/",
        "https://docs.python.org/3/tutorial/",
        "https://fastapi.tiangolo.com/",
    ]


def test_page_and_format():
    assert page_for_result(1) == 1
    assert page_for_result(10) == 1
    assert page_for_result(11) == 2
    assert page_for_result(23) == 3
    hit = RankHit(
        keyword="python",
        found=True,
        result_number=23,
        page_number=3,
        matched_url="https://www.python.org/",
        note="Result #23, page 3",
    )
    assert format_rank(hit) == "Result #23, page 3"


def test_hit_from_urls_finds_first_match():
    hit = hit_from_urls(
        "python",
        "https://python.org",
        [
            "https://en.wikipedia.org/wiki/Python",
            "https://docs.python.org/3/",
            "https://www.python.org/",
        ],
        "DuckDuckGo",
    )
    assert hit.found is True
    assert hit.result_number == 2
    assert hit.page_number == 1
    assert hit.matched_url == "https://docs.python.org/3/"


def test_lookup_uses_duckduckgo_only(monkeypatch):
    monkeypatch.setattr(
        "app.ranking.rank_with_duckduckgo",
        lambda keyword, target: RankHit(
            keyword=keyword,
            found=True,
            result_number=1,
            page_number=1,
            matched_url="https://www.python.org/",
            note="Result #1, page 1",
        ),
    )
    report = lookup_ranks(["python"], "python.org")
    assert report.source == "duckduckgo"
    assert report.notice is None
    assert report.results[0].result_number == 1
    assert report.url == "https://python.org"
