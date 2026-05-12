import json
import os
import re
import time
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
        pw("goto", _LISTING_URL)
        time.sleep(2)

        all_urls: list[str] = []
        stop = False
        max_show_more = 20
        current_day: date | None = None

        # JS: wait for the "Show More" button (signals full list render), then extract all
        # premium article links that contain a YYYY/MM/DD date segment.
        # Covers both /coverage/ and /earnings/call-transcripts/ URL shapes.
        _extract_js = (
            "async page => {\n"
            "  try {\n"
            "    await page.waitForFunction(\n"
            "      () => [...document.querySelectorAll('button')]"
            ".some(b => /show more/i.test(b.innerText)),\n"
            "      { timeout: 15000 }\n"
            "    );\n"
            "  } catch(e) {}\n"
            "  return await page.evaluate(() => {\n"
            "    const seen = new Set();\n"
            "    return [...document.querySelectorAll('a[href*=\"/premium/\"]')]\n"
            "      .filter(a => !a.href.includes('#') && a.innerText.trim().length > 3)\n"
            "      .map(a => {\n"
            "        const m = a.href.match(/\\/([0-9]{4})\\/([0-9]{2})\\/([0-9]{2})\\//);\n"
            "        return { href: a.href, date: m ? `${m[1]}-${m[2]}-${m[3]}` : '' };\n"
            "      })\n"
            "      .filter(x => x.date && !seen.has(x.href) && seen.add(x.href));\n"
            "  });\n"
            "}"
        )

        for _ in range(max_show_more):
            raw = pw("run-code", _extract_js)

            try:
                items = json.loads(raw.strip())
                if isinstance(items, str):
                    items = json.loads(items)
            except (json.JSONDecodeError, TypeError):
                break

            for item in items:
                href = item.get("href", "")
                item_date_str = item.get("date", "")
                if not href or not item_date_str:
                    continue
                try:
                    item_date = date.fromisoformat(item_date_str)
                except ValueError:
                    continue
                if current_day is None:
                    current_day = item_date
                if item_date < current_day:
                    stop = True
                    break
                if href not in all_urls:
                    all_urls.append(href)

            if stop:
                break

            # Click "Show More" to load the next batch of articles
            has_more = pw(
                "run-code",
                "async page => {\n"
                "  const btn = page.getByRole('button', { name: /show more/i });\n"
                "  try {\n"
                "    await btn.waitFor({ timeout: 5000 });\n"
                "    await btn.scrollIntoViewIfNeeded();\n"
                "    await btn.click();\n"
                "    await page.waitForTimeout(2000);\n"
                "    return 'true';\n"
                "  } catch(e) {\n"
                "    return 'false';\n"
                "  }\n"
                "}",
            )
            if "true" not in has_more:
                break

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
