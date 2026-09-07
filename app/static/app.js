const MAX_KEYWORDS = 8;

const form = document.getElementById("rank-form");
const keywordsInput = document.getElementById("keywords");
const urlInput = document.getElementById("url");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const tableWrap = document.getElementById("table-wrap");
const resultsBody = document.getElementById("results-body");
const tableCaption = document.getElementById("table-caption");
const keywordCountEl = document.getElementById("keyword-count");

function setStatus(message, kind) {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`;
}

function parseKeywords(raw) {
  const seen = new Set();
  const keywords = [];
  for (const part of raw.split(",")) {
    const keyword = part.trim().replace(/\s+/g, " ");
    if (!keyword) continue;
    const key = keyword.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    keywords.push(keyword);
  }
  return keywords;
}

function updateKeywordCount() {
  const count = parseKeywords(keywordsInput.value).length;
  keywordCountEl.textContent = `${count} / ${MAX_KEYWORDS} keywords`;
  keywordCountEl.classList.toggle("over", count > MAX_KEYWORDS);
}

keywordsInput.addEventListener("input", updateKeywordCount);
updateKeywordCount();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const keywords = keywordsInput.value.trim();
  const url = urlInput.value.trim();
  const parsed = parseKeywords(keywords);

  if (!parsed.length) {
    setStatus("Enter at least one keyword.", "error");
    keywordsInput.focus();
    return;
  }
  if (parsed.length > MAX_KEYWORDS) {
    setStatus(
      `Please enter at most ${MAX_KEYWORDS} keywords so lookups stay reliable.`,
      "error"
    );
    keywordsInput.focus();
    return;
  }
  if (!url) {
    setStatus("Enter a website URL.", "error");
    urlInput.focus();
    return;
  }

  const count = parsed.length;
  submitBtn.disabled = true;
  tableWrap.hidden = true;
  resultsBody.replaceChildren();
  setStatus(
    `Checking ${count} keyword${count === 1 ? "" : "s"} on DuckDuckGo. This can take a little while.`,
    "loading"
  );

  try {
    const response = await fetch("/api/rank", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords, url }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || "Lookup failed.";
      throw new Error(typeof detail === "string" ? detail : "Lookup failed.");
    }

    renderResults(payload);
    const found = payload.results.filter((row) => row.found).length;
    setStatus(
      payload.notice ||
        `Finished via DuckDuckGo. ${found} of ${payload.results.length} keyword${
          payload.results.length === 1 ? "" : "s"
        } ranked in the checked results.`,
      payload.notice ? "notice" : "idle"
    );
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    submitBtn.disabled = false;
  }
});

function renderResults(payload) {
  tableCaption.textContent = `DuckDuckGo positions for ${payload.url}`;
  const positionHeader = document.querySelector("thead th:last-child");
  if (positionHeader) {
    positionHeader.textContent = "Search position";
  }
  resultsBody.replaceChildren();

  for (const row of payload.results) {
    const tr = document.createElement("tr");

    const keywordCell = document.createElement("td");
    keywordCell.className = "keyword";
    keywordCell.textContent = row.keyword;

    const positionCell = document.createElement("td");
    positionCell.className = "position";

    const badge = document.createElement("span");
    badge.className = row.found ? "found" : "missing";
    badge.textContent = row.position;
    positionCell.append(badge);

    if (row.matched_url) {
      const link = document.createElement("a");
      link.href = row.matched_url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = row.matched_url;
      positionCell.append(link);
    }

    tr.append(keywordCell, positionCell);
    resultsBody.append(tr);
  }

  tableWrap.hidden = false;
}
