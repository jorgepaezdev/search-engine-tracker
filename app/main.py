from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.ranking import format_rank, lookup_ranks, parse_keywords

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Search Engine Tracker", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


class RankRequest(BaseModel):
    keywords: str = Field(..., min_length=1, max_length=2000)
    url: str = Field(..., min_length=1, max_length=2000)


class RankRow(BaseModel):
    keyword: str
    found: bool
    result_number: Optional[int]
    page_number: Optional[int]
    matched_url: Optional[str]
    position: str


class RankResponse(BaseModel):
    url: str
    source: str
    notice: Optional[str] = None
    results: list[RankRow]


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/rank", response_model=RankResponse)
def rank(payload: RankRequest) -> RankResponse:
    keywords = parse_keywords(payload.keywords)
    if not keywords:
        raise HTTPException(status_code=400, detail="Enter at least one keyword.")
    if len(keywords) > 8:
        raise HTTPException(
            status_code=400,
            detail="Please enter at most 8 keywords so DuckDuckGo lookups stay reliable.",
        )

    try:
        report = lookup_ranks(keywords, payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail="Could not complete the search lookup. Try again in a moment.",
        ) from exc

    return RankResponse(
        url=report.url,
        source=report.source,
        notice=report.notice,
        results=[
            RankRow(
                keyword=hit.keyword,
                found=hit.found,
                result_number=hit.result_number,
                page_number=hit.page_number,
                matched_url=hit.matched_url,
                position=format_rank(hit),
            )
            for hit in report.results
        ],
    )
