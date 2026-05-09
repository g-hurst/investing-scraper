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


@router.get("", response_model=ArticleList, operation_id="list_articles")
def list_articles(
    source: str | None = Query(None),
    ticker: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
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


@router.get("/{article_id}", response_model=ArticleDetail, operation_id="get_article")
def get_article(article_id: int):
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
