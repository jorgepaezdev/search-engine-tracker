# Search Engine Tracker

Python 3.10 web app that checks where a website ranks for a list of keywords on DuckDuckGo.

## What it does

1. Enter **keywords** separated by commas.
2. Enter the **URL** of the site you want to find.
3. Click **Submit**.
4. The app looks up each keyword on DuckDuckGo and shows a table:

| Keyword | Search position |
| --- | --- |
| python web framework | Result #4, page 1 |
| obscure phrase | Not found in the first 50 DuckDuckGo results |

The left column is the keyword. The right column is the organic result number and the page (10 results per page). If the site appears, the matching result URL is linked under the position.

Lookups use **DuckDuckGo** web results.

## Requirements

This app is pinned to **Python 3.10**. Local runs, CI, Docker, and PaaS deploys (`runtime.txt`) all use that interpreter.

## Run locally

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 48621
```

Open [http://127.0.0.1:48621](http://127.0.0.1:48621).

## Tests

```bash
python3.10 -m pytest -q
```

## Notes

- Keep the keyword list to 8 or fewer. Each keyword is checked in sequence.
- Ranking uses the first organic result whose host matches the submitted site, including subdomains (`docs.example.com` matches `example.com`).
- DuckDuckGo lookups typically cover the first few dozen results (up to 50).
