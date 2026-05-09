import time
from datetime import date

from dotenv import load_dotenv

from scraper.playwright_utils import pw
from scraper.sources.motley_fool import MotleyFool
from scraper.storage import load_state, save_article, save_state

load_dotenv()

SOURCES = [
    MotleyFool(),
    # Add new sources here, e.g.: SeekingAlpha(), Barrons()
]


def run() -> None:
    for source in SOURCES:
        state = load_state(source.source_id)
        print(f"[{source.source_id}] Last scrape: {state['last_scrape']}")

        try:
            source.ensure_authenticated()
        except Exception as e:
            print(f"[{source.source_id}] Authentication failed: {e}")
            continue

        try:
            urls = source.get_new_article_urls(state["last_scrape"])
        except Exception as e:
            print(f"[{source.source_id}] Failed to discover articles: {e}")
            continue

        # Filter already-scraped URLs
        new_urls = [u for u in urls if u not in state["scraped_urls"]]
        print(f"[{source.source_id}] Found {len(new_urls)} new article(s)")

        scraped = 0
        for url in new_urls:
            try:
                article = source.scrape_article(url)
                article_id = save_article(source.source_id, article)
                state["scraped_urls"].add(url)
                scraped += 1
                print(f"  Saved: [{article_id}] {article.get('title', url)}")
            except Exception as e:
                print(f"  Skipped {url}: {e}")
            time.sleep(2)

        state["last_scrape"] = date.today()
        save_state(source.source_id, state)
        print(f"[{source.source_id}] Done. Scraped {scraped} article(s).")

    try:
        pw("close")
    except Exception:
        pass


if __name__ == "__main__":
    run()
