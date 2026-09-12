from app.ranking import (
    extract_bing_rss_urls,
    extract_organic_urls,
    format_rank,
    hit_from_urls,
    next_page_payload,
    page_for_result,
    parse_engine,
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


def test_next_page_payload_reads_ddg_form():
    html = """
    <form action="/html/" method="post">
      <input type="submit" value="Next" />
      <input name="q" value="fastapi" />
      <input name="s" value="10" />
      <input name="vqd" value="abc" />
      <input name="kl" value="us-en" />
    </form>
    """
    payload = next_page_payload(html)
    assert payload is not None
    assert payload["q"] == "fastapi"
    assert payload["s"] == "10"
    assert payload["vqd"] == "abc"


def test_parse_engine_accepts_aliases():
    assert parse_engine("DuckDuckGo") == "duckduckgo"
    assert parse_engine("ddg") == "duckduckgo"
    assert parse_engine("Bing") == "bing"


def test_parse_engine_rejects_unknown():
    try:
        parse_engine("google")
    except ValueError as exc:
        assert "DuckDuckGo or Bing" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_extract_bing_rss_urls():
    xml = """
    <rss><channel>
      <item><title>Python</title><link>https://www.python.org/</link></item>
      <item><title>Docs</title><link>https://docs.python.org/3/</link></item>
      <item><title>Bing</title><link>https://www.bing.com/search</link></item>
    </channel></rss>
    """
    assert extract_bing_rss_urls(xml) == [
        "https://www.python.org/",
        "https://docs.python.org/3/",
    ]


def test_lookup_uses_selected_engine(monkeypatch):
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def rank(self, keyword, target, max_results=50):
            return RankHit(
                keyword=keyword,
                found=True,
                result_number=1,
                page_number=1,
                matched_url="https://www.python.org/",
                note="Result #1, page 1",
            )

    monkeypatch.setattr("app.ranking.DuckDuckGoClient", lambda: FakeClient())
    monkeypatch.setattr("app.ranking.BingClient", lambda: FakeClient())

    ddg = lookup_ranks(["python"], "python.org", engine="duckduckgo")
    assert ddg.source == "duckduckgo"
    assert ddg.results[0].result_number == 1
    assert ddg.url == "https://python.org"

    bing = lookup_ranks(["python"], "python.org", engine="bing")
    assert bing.source == "bing"
    assert bing.results[0].result_number == 1
