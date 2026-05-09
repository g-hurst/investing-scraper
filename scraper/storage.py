import os
from datetime import date, datetime, timedelta, timezone

import psycopg2


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def load_state(source_id: str) -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_scrape FROM scrape_state WHERE source_id = %s",
                (source_id,),
            )
            row = cur.fetchone()
            last_scrape = row[0] if row else date.today() - timedelta(days=30)

            cur.execute(
                "SELECT url FROM articles WHERE source = %s",
                (source_id,),
            )
            scraped_urls = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    return {"last_scrape": last_scrape, "scraped_urls": scraped_urls}


def save_state(source_id: str, state: dict) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scrape_state (source_id, last_scrape)
                VALUES (%s, %s)
                ON CONFLICT (source_id) DO UPDATE SET last_scrape = EXCLUDED.last_scrape
                """,
                (source_id, state["last_scrape"]),
            )
        conn.commit()
    finally:
        conn.close()


def save_article(source_id: str, article: dict) -> int | None:
    pub_date = article.get("published_date") or None
    scraped_at = article.get("scraped_at")
    if scraped_at:
        try:
            scraped_at = datetime.fromisoformat(scraped_at.rstrip("Z")).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            scraped_at = None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles (source, url, title, published_date, author, content, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
                """,
                (
                    source_id,
                    article.get("url", ""),
                    article.get("title", ""),
                    pub_date or None,
                    article.get("author") or None,
                    article.get("content") or None,
                    scraped_at,
                ),
            )
            row = cur.fetchone()
            if row is None:
                return None  # duplicate URL, skipped
            article_id = row[0]

            tickers = article.get("tickers", [])
            if tickers:
                cur.executemany(
                    """
                    INSERT INTO article_tickers (article_id, ticker)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [(article_id, t) for t in tickers],
                )

        conn.commit()
        return article_id
    finally:
        conn.close()
