from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.models import ArticleDetail, ArticleList, ArticleSummary
from scraper.storage import get_conn

router = APIRouter()

_ARTICLE_COLS = """
    a.id, a.source, a.url, a.title, a.published_date, a.author, a.scraped_at,
    COALESCE(
        array_agg(t.ticker ORDER BY t.ticker) FILTER (WHERE t.ticker IS NOT NULL),
        '{}'
    ) AS tickers
"""

_ARTICLE_FROM = """
    FROM articles a
    LEFT JOIN article_tickers t ON t.article_id = a.id
"""


def _build_where(source, ticker, date_from, date_to):
    conditions = []
    params = []
    if source:
        conditions.append("a.source = %s")
        params.append(source)
    if ticker:
        conditions.append("a.id IN (SELECT article_id FROM article_tickers WHERE ticker = %s)")
        params.append(ticker.upper())
    if date_from:
        conditions.append("a.published_date >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("a.published_date <= %s")
        params.append(date_to)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


def _row_to_summary(row) -> ArticleSummary:
    return ArticleSummary(
        id=row[0],
        source=row[1],
        url=row[2],
        title=row[3],
        published_date=row[4],
        author=row[5],
        scraped_at=row[6],
        tickers=list(row[7]),
    )


@router.get("", response_model=ArticleList, operation_id="stocknews_list_articles")
def list_articles(
    source: str | None = Query(None, description="Filter by news source identifier (e.g. 'motley_fool')"),
    ticker: str | None = Query(None, description="Filter by stock ticker symbol, case-insensitive (e.g. 'NVDA')"),
    date_from: date | None = Query(None, description="Include only articles published on or after this date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Include only articles published on or before this date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500, description="Number of results per page (1–500, default 100)"),
    offset: int = Query(0, ge=0, description="Number of results to skip for pagination (default 0)"),
):
    """List scraped news articles with optional filters.

    Returns a paginated list of article summaries (no full content). Combine
    filters freely: use ticker to find all news for a stock, source to narrow
    to one publisher, or date_from/date_to to focus on a period. Results are
    sorted by published_date descending (newest first). Call
    stocknews_get_article with an article ID to retrieve the full body text.
    """
    where, params = _build_where(source, ticker, date_from, date_to)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(DISTINCT a.id) {_ARTICLE_FROM} {where}",
                params,
            )
            total = cur.fetchone()[0]

            cur.execute(
                f"SELECT {_ARTICLE_COLS} {_ARTICLE_FROM} {where} "
                f"GROUP BY a.id ORDER BY a.published_date DESC NULLS LAST, a.scraped_at DESC "
                f"LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return ArticleList(total=total, items=[_row_to_summary(r) for r in rows])


def _build_search_where(q, source, ticker, date_from, date_to):
    where, params = _build_where(source, ticker, date_from, date_to)
    search_param = f"%{q}%"
    condition = "(a.title ILIKE %s OR a.content ILIKE %s)"
    where = f"{where} AND {condition}" if where else f"WHERE {condition}"
    return where, params + [search_param, search_param]


@router.get("/search", response_model=ArticleList, operation_id="stocknews_search_articles")
def search_articles(
    q: str = Query(..., description="Keyword to search for in article title and content (case-insensitive substring match)"),
    source: str | None = Query(None, description="Filter by news source identifier (e.g. 'motley_fool')"),
    ticker: str | None = Query(None, description="Also filter by stock ticker symbol (case-insensitive)"),
    date_from: date | None = Query(None, description="Include only articles published on or after this date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Include only articles published on or before this date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500, description="Number of results per page (1–500, default 100)"),
    offset: int = Query(0, ge=0, description="Number of results to skip for pagination (default 0)"),
):
    """Search articles by keyword across title and content.

    Performs a case-insensitive substring search (ILIKE) across article titles
    and full body text. Combine with ticker, source, and date filters to narrow
    results further. Useful when you have a topic or company name but not a
    ticker symbol. Returns the same ArticleList shape as stocknews_list_articles.
    """
    where, params = _build_search_where(q, source, ticker, date_from, date_to)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(DISTINCT a.id) {_ARTICLE_FROM} {where}", params)
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_ARTICLE_COLS} {_ARTICLE_FROM} {where} "
                f"GROUP BY a.id ORDER BY a.published_date DESC NULLS LAST, a.scraped_at DESC "
                f"LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return ArticleList(total=total, items=[_row_to_summary(r) for r in rows])


@router.get("/{article_id}", response_model=ArticleDetail, operation_id="stocknews_get_article")
def get_article(article_id: int):
    """Retrieve a single article's full content by ID.

    Returns all fields including the complete article body text. Use
    stocknews_list_articles or stocknews_search_articles first to discover
    article IDs, then call this to fetch the full content for reading or
    analysis.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_ARTICLE_COLS}, a.content {_ARTICLE_FROM} "
                f"WHERE a.id = %s GROUP BY a.id",
                (article_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return ArticleDetail(
        id=row[0],
        source=row[1],
        url=row[2],
        title=row[3],
        published_date=row[4],
        author=row[5],
        scraped_at=row[6],
        tickers=list(row[7]),
        content=row[8],
    )
