from fastapi.testclient import TestClient

from app.main import app
from app.ranking import RankHit, RankReport


client = TestClient(app)


def test_home_renders_fields():
    response = client.get("/")
    assert response.status_code == 200
    assert "Search Engine Tracker" in response.text
    assert "DuckDuckGo" in response.text
    assert "Keywords" in response.text
    assert "URL" in response.text
    assert "Submit" in response.text
    assert "max 8" in response.text
    assert "keyword-count" in response.text
    assert "google" not in response.text.lower()


def test_rank_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.main.lookup_ranks",
        lambda keywords, url: RankReport(
            url="https://www.python.org/",
            source="duckduckgo",
            notice=None,
            results=[
                RankHit(
                    keyword="python",
                    found=True,
                    result_number=1,
                    page_number=1,
                    matched_url="https://www.python.org/",
                    note="Result #1, page 1",
                )
            ],
        ),
    )
    response = client.post(
        "/api/rank",
        json={"keywords": "python, python", "url": "python.org"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "https://www.python.org/"
    assert payload["source"] == "duckduckgo"
    assert payload["results"][0]["keyword"] == "python"
    assert payload["results"][0]["position"] == "Result #1, page 1"


def test_rank_rejects_empty_keywords():
    response = client.post("/api/rank", json={"keywords": " , , ", "url": "https://example.com"})
    assert response.status_code == 400


def test_rank_rejects_too_many_keywords():
    keywords = ", ".join(f"keyword {index}" for index in range(9))
    response = client.post(
        "/api/rank",
        json={"keywords": keywords, "url": "https://example.com"},
    )
    assert response.status_code == 400
    assert "at most 8" in response.json()["detail"]
