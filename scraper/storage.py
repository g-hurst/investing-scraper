import json
import re
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_STATE_FILE = _ROOT / "data" / "state.json"
_ARTICLES_DIR = _ROOT / "data" / "articles"


def load_state(source_id: str) -> dict:
    if _STATE_FILE.exists():
        raw = json.loads(_STATE_FILE.read_text())
    else:
        raw = {}

    source_state = raw.get(source_id, {})
    last_scrape_str = source_state.get("last_scrape")
    last_scrape = (
        date.fromisoformat(last_scrape_str)
        if last_scrape_str
        else date.fromordinal(date.today().toordinal() - 30)
    )
    return {
        "last_scrape": last_scrape,
        "scraped_urls": set(source_state.get("scraped_urls", [])),
    }


def save_state(source_id: str, state: dict) -> None:
    if _STATE_FILE.exists():
        raw = json.loads(_STATE_FILE.read_text())
    else:
        raw = {}

    raw[source_id] = {
        "last_scrape": state["last_scrape"].isoformat(),
        "scraped_urls": sorted(state["scraped_urls"]),
    }
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(raw, indent=2))


def save_article(source_id: str, article: dict) -> Path:
    _ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    pub_date = article.get("published_date", "unknown")
    slug = _slugify(article.get("title", "untitled"))[:60]
    filename = f"{pub_date}_{source_id}_{slug}.json"
    path = _ARTICLES_DIR / filename
    path.write_text(json.dumps(article, indent=2, ensure_ascii=False))
    return path


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")
