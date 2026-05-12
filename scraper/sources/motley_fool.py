import json
import os
import re
import time
import urllib.parse
from datetime import date, datetime
from pathlib import Path

from scraper.playwright_utils import pw
from scraper.sources.base import BaseSource

_AUTH_STATE = str(Path(__file__).parent.parent.parent / "data" / "auth" / "motley_fool.json")
_LISTING_URL = "https://www.fool.com/premium/news-and-analysis/articles"
_LOGIN_ENTRY = "https://www.fool.com/premium"

# Matches "(NASDAQ: KRYS)" or "(NYSE: BIP)" style ticker markup
_EXCHANGE_TICKER_RE = re.compile(r'\((?:NASDAQ|NYSE|NYSEARCA|OTC):\s*([A-Z]{1,5})\)')

# JS regex to extract YYYY/MM/DD from article URLs — \d must be \\d in Python string
_JS_URL_DATE_RE = r"/\/coverage\/(?:updates\/)?([0-9]{4}\/[0-9]{2}\/[0-9]{2})\//g"
_JS_DATE_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


class MotleyFool(BaseSource):
    source_id = "motley_fool"
    auth_state_path = _AUTH_STATE

    def ensure_authenticated(self) -> None:
        auth_path = Path(_AUTH_STATE)

        # Always open a fresh browser context first
        pw("open", "about:blank")

        if auth_path.exists():
            pw("state-load", _AUTH_STATE)
            pw("goto", _LISTING_URL)
            time.sleep(2)
            snapshot = pw("snapshot")
            if "coverage" in snapshot.lower():
                print("[motley_fool] Using cached session.")
                return
            print("[motley_fool] Cached session expired, re-authenticating...")

        email = os.environ["MOTLEY_FOOL_EMAIL"]
        password = os.environ["MOTLEY_FOOL_PASSWORD"]

        # Navigating to /premium triggers the auth.fool.com redirect
        pw("goto", _LOGIN_ENTRY)
        time.sleep(2)

        # Step 1: email
        pw("run-code", f"""async page => {{
            await page.getByRole('textbox', {{ name: /username|email/i }}).fill({json.dumps(email)});
            await page.getByRole('button', {{ name: /continue/i }}).click();
            await page.waitForLoadState('networkidle', {{ timeout: 10000 }}).catch(() => {{}});
        }}""")
        time.sleep(1)

        # Step 2: password
        pw("run-code", f"""async page => {{
            await page.getByRole('textbox', {{ name: /password/i }}).fill({json.dumps(password)});
            await page.getByRole('button', {{ name: /continue/i }}).click();
            await page.waitForLoadState('networkidle', {{ timeout: 15000 }}).catch(() => {{}});
        }}""")
        time.sleep(2)

        Path(_AUTH_STATE).parent.mkdir(parents=True, exist_ok=True)
        pw("state-save", _AUTH_STATE)
        print("[motley_fool] Authenticated and session saved.")

    def get_new_article_urls(self, since_date: date) -> list[str]:
        # Navigate to the listing page so the browser acquires auth tokens,
        # then intercept the first FilteredArticleList request to capture them.
        capture_js = (
            "async page => {\n"
            "  let captured = null;\n"
            "  const handler = req => {\n"
            "    if (req.url().includes('FilteredArticleList') && !captured)\n"
            "      captured = { headers: req.headers(), url: req.url() };\n"
            "  };\n"
            "  page.on('request', handler);\n"
            "  await page.goto(" + json.dumps(_LISTING_URL) + ");\n"
            "  await page.waitForFunction(\n"
            "    () => [...document.querySelectorAll('button')].some(b => /show more/i.test(b.innerText)),\n"
            "    { timeout: 15000 }\n"
            "  ).catch(() => {});\n"
            "  page.off('request', handler);\n"
            "  return JSON.stringify(captured || {});\n"
            "}"
        )
        raw_captured = pw("run-code", capture_js)
        try:
            captured = json.loads(raw_captured.strip())
            if isinstance(captured, str):
                captured = json.loads(captured)
        except (json.JSONDecodeError, TypeError):
            captured = {}

        api_headers = captured.get("headers", {})
        if not api_headers:
            raise RuntimeError("Could not capture API auth headers from page request")

        # Extract the persisted query hash from the intercepted request URL
        _sha256_hash = "8f705b5b30393d22fd4f16856d283a7da8f00bf2153d86fafeffb43c825d095e"
        try:
            captured_url = captured.get("url", "")
            ext_param = urllib.parse.parse_qs(urllib.parse.urlparse(captured_url).query).get("extensions", [""])[0]
            ext_json = json.loads(urllib.parse.unquote(ext_param))
            _sha256_hash = ext_json["persistedQuery"]["sha256Hash"]
        except Exception:
            pass  # fall back to hardcoded hash

        _API_EXT = json.dumps({
            "clientLibrary": {"name": "@apollo/client", "version": "4.1.6"},
            "persistedQuery": {
                "version": 1,
                "sha256Hash": _sha256_hash,
            },
        })
        _API_BASE_VARS = {
            "tagsFilterType": "OR",
            "videoInclusion": "EXCLUDE",
            "includeImages": False,
            "includeFreeContent": False,
            "includeStaticPages": True,
            "limit": 20,
            "myStocks": False,
            "orderBy": "",
            "tags": [],
            "tagCollectionSlugs": [],
            "productIds": [],
            "authorIds": [],
        }

        all_urls: list[str] = []
        offset = 0

        while True:
            api_url = (
                "https://api.fool.com/premium-graphql-proxy/graphql"
                "?operationName=FilteredArticleList"
                "&variables=" + urllib.parse.quote(json.dumps({**_API_BASE_VARS, "offset": offset}))
                + "&extensions=" + urllib.parse.quote(_API_EXT)
            )
            fetch_js = (
                "async page => {\n"
                f"  const url = {json.dumps(api_url)};\n"
                f"  const headers = {json.dumps(api_headers)};\n"
                "  return await page.evaluate(async ({ url, headers }) => {\n"
                "    const r = await fetch(url, { headers });\n"
                "    return await r.text();\n"
                "  }, { url, headers });\n"
                "}"
            )
            raw = pw("run-code", fetch_js)
            try:
                resp = json.loads(raw.strip())
                if isinstance(resp, str):
                    resp = json.loads(resp)
            except (json.JSONDecodeError, TypeError):
                break

            contents = resp.get("data", {}).get("contents", [])
            if not contents:
                break

            stop = False
            for item in contents:
                path = item.get("path", "")
                publish_at = item.get("publishAt", "")
                if not path or not publish_at:
                    continue
                try:
                    item_date = date.fromisoformat(publish_at[:10])
                except ValueError:
                    continue
                if item_date < since_date:
                    stop = True
                    break
                url = "https://www.fool.com/premium" + path.rstrip("/")
                if url not in all_urls:
                    all_urls.append(url)

            if stop or len(contents) < _API_BASE_VARS["limit"]:
                break

            offset += _API_BASE_VARS["limit"]

        return all_urls

    def scrape_article(self, url: str) -> dict:
        pw("goto", url)
        time.sleep(2)

        # Returns object directly (no JSON.stringify) so --raw gives parseable JSON
        _article_js = (
            "async page => {\n"
            "  return await page.evaluate(() => {\n"
            "    const article = document.querySelector('article');\n"
            "    if (!article) return { error: 'no article element' };\n"
            "    const title = article.querySelector('h1')?.innerText?.trim() || '';\n"
            "    const authorEl = article.querySelector('a[href*=\"investor-profile\"]');\n"
            "    const author = authorEl?.innerText?.trim() || '';\n"
            "    let pubDate = '';\n"
            "    for (const p of [...article.querySelectorAll('p')]) {\n"
            "      const m = p.innerText.trim().match(\n"
            "        /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+[0-9]+,\\s+[0-9]{4}/\n"
            "      );\n"
            "      if (m) { pubDate = p.innerText.trim(); break; }\n"
            "    }\n"
            "    const tickerTexts = [...document.querySelectorAll('[class*=\"ticker\"]')]\n"
            "      .map(el => el.innerText.trim()).filter(Boolean);\n"
            "    const content = article.innerText.trim();\n"
            "    return { title, author, pubDate, tickerTexts, content };\n"
            "  });\n"
            "}"
        )

        try:
            raw = pw("run-code", _article_js)
            data = json.loads(raw.strip())
            if isinstance(data, str):
                data = json.loads(data)
        except Exception:
            data = {}

        if "error" in data:
            print(f"  Warning: {data['error']} at {url}")

        ticker_texts = data.get("tickerTexts", [])
        tickers = sorted({
            m.group(1)
            for t in ticker_texts
            for m in [_EXCHANGE_TICKER_RE.search(t)]
            if m
        })

        pub_date = _parse_article_date(data.get("pubDate", ""), url)

        return {
            "source": self.source_id,
            "url": url,
            "title": data.get("title", ""),
            "published_date": pub_date.isoformat() if pub_date else "",
            "author": data.get("author", ""),
            "tickers": tickers,
            "content": data.get("content", ""),
            "scraped_at": datetime.utcnow().isoformat() + "Z",
        }


def _parse_article_date(raw: str, url: str = "") -> date | None:
    if raw:
        m = re.match(r"(\w+ \d+, \d{4})", raw)
        if m:
            for fmt in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    return datetime.strptime(m.group(1), fmt).date()
                except ValueError:
                    pass

    # Fallback: parse YYYY/MM/DD directly from the URL
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None
